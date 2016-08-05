""" Adyen payment processing. """
from __future__ import unicode_literals

from datetime import datetime
import json
import logging
from urlparse import urljoin

from oscar.apps.payment.exceptions import GatewayError, TransactionDeclined
from oscar.core.loading import get_model
import requests

from ecommerce.core.constants import ISO_8601_FORMAT
from ecommerce.extensions.order.constants import PaymentEventTypeName
from ecommerce.extensions.payment.processors.base import BasePaymentProcessor
from ecommerce.extensions.payment.processors.adyen.exceptions import (
    AdyenRequestError,
    MissingAdyenEventCodeException,
    UnsupportedAdyenEventException
)
from ecommerce.extensions.payment.utils import minor_units
from ecommerce.extensions.refund.status import REFUND

logger = logging.getLogger(__name__)

PaymentEvent = get_model('order', 'PaymentEvent')
PaymentEventType = get_model('order', 'PaymentEventType')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')
ProductClass = get_model('catalogue', 'ProductClass')
Source = get_model('payment', 'Source')
SourceType = get_model('payment', 'SourceType')


class Adyen(BasePaymentProcessor):
    """
    Adyen CSE Integration (June 2016)

    For reference, see https://docs.adyen.com/developers
    """

    BASKET_TEMPLATE = 'adyen/basket.html'
    CONFIGURATION_MODEL = 'ecommerce.extensions.payment.processors.adyen.models.AdyenConfiguration'
    NAME = 'adyen'
    URLS_MODULE = 'ecommerce.extensions.payment.processors.adyen.urls'

    @property
    def generation_time(self):
        return datetime.utcnow().strftime(ISO_8601_FORMAT)

    def get_alternative_payment_methods(self, basket):
        return ['hello']

    def get_transaction_parameters(self, basket, request=None):
        """
        Generate a dictionary of parameters Adyen requires to complete a transaction.

        Arguments:
            basket (Basket): The basket of products being purchase.; not used by this method.

        Keyword Arguments:
            request (Request): A Request object which could be used to construct an absolute URL; not
                used by this method.

        Returns:
            dict: Adyen-specific parameters required to complete a transaction.
        """
        parameters = {
            'payment_page_url': '',
        }

        return parameters

    def authorise(self, basket, encrypted_card_data, **shopper_data):
        """
        Send authorise API request to Adyen to authorize payment.
        """
        request_url = urljoin(self.configuration.payment_api_url, 'authorise')
        request_payload = {
            'additionalData': {
                'card.encrypted.json': encrypted_card_data
            },
            'amount': {
                'value': minor_units(basket.total_incl_tax, basket.currency),
                'currency': basket.currency
            },
            'reference': basket.order_number,
            'merchantAccount': self.configuration.merchant_account_code
        }

        # Add additional shopper data collected on payment form
        request_payload.update(_get_shopper_data(**shopper_data))

        response = requests.post(
            request_url,
            auth=(self.configuration.web_service_username, self.configuration.web_service_password),
            headers={
                'Content-Type': 'application/json'
            },
            json=request_payload
        )

        adyen_response = response.json()
        adyen_response['eventCode'] = 'AUTHORISATION'

        if response.status_code != requests.codes.OK:
            message = 'Request for basket {basket} to {url} returned with {status} {response}'.format(
                basket=basket.order_number,
                url=request_url,
                status=response.status_code,
                response=json.dumps(adyen_response)
            )
            logger.exception(message)
            raise AdyenRequestError(message, adyen_response)

        return adyen_response

    def handle_processor_response(self, response, basket=None):
        """
        Handle notification/response from Adyen.

        This method does the following:
            1. Create PaymentEvents and Sources for successful payments.

        Arguments:
            response (dict): Dictionary of parameters received from the payment processor.

        Keyword Arguments:
            basket (Basket): Basket being purchased via the payment processor.

        Raises:
            UserCancelled: Indicates the user cancelled payment.
            TransactionDeclined: Indicates the payment was declined by the processor.
            GatewayError: Indicates a general error on the part of the processor.
            InvalidAdyenDecision: Indicates an unknown decision value.
                Known values are ACCEPT, CANCEL, DECLINE, ERROR.
            PartialAuthorizationError: Indicates only a portion of the requested amount was authorized.
        """
        try:
            event_code = response['eventCode']
            psp_reference = response['pspReference']
            return getattr(self, '_handle_{event}'.format(event=event_code.lower()))(psp_reference, response, basket)
        except KeyError:
            raise MissingAdyenEventCodeException
        except AttributeError:
            raise UnsupportedAdyenEventException

    def _handle_authorisation(self, psp_reference, response, basket):
        """
        Handle an authorise response from Adyen.

        This method does the following:
            1. Create PaymentEvents and Sources for successful payments.

        Arguments:
            response (dict): Dictionary of parameters received from the payment processor.

        Keyword Arguments:
            basket (Basket): Basket being purchased via the payment processor.

        Raises:
            UserCancelled: Indicates the user cancelled payment.
            TransactionDeclined: Indicates the payment was declined by the processor.
            GatewayError: Indicates a general error on the part of the processor.
            InvalidAdyenDecision: Indicates an unknown decision value.
                Known values are ACCEPT, CANCEL, DECLINE, ERROR.
            PartialAuthorizationError: Indicates only a portion of the requested amount was authorized.
        """

        # Raise an exception for payments that were not accepted. Consuming code should be responsible for handling
        # and logging the exception.
        result_code = response['resultCode'].lower()
        if result_code != 'authorised':
            raise TransactionDeclined

        # Create Source to track all transactions related to this processor and order
        source_type, __ = SourceType.objects.get_or_create(name=self.NAME)
        currency = basket.currency
        total = basket.total_incl_tax

        source = Source(source_type=source_type,
                        currency=currency,
                        amount_allocated=total,
                        amount_debited=total,
                        reference=psp_reference)

        # Create PaymentEvent to track
        event_type, __ = PaymentEventType.objects.get_or_create(name=PaymentEventTypeName.PAID)
        event = PaymentEvent(event_type=event_type, amount=total, reference=psp_reference, processor_name=self.NAME)

        return source, event

    def _handle_cancel_or_refund(self, psp_reference, response, basket):
        order = basket.order_set.first()
        # TODO Update this if we ever support multiple payment sources for a single order.
        source = order.sources.first()
        refund = order.refunds.get(status__in=[REFUND.PENDING_WITH_REVOCATION, REFUND.PENDING_WITHOUT_REVOCATION])
        amount = refund.total_credit_excl_tax
        if response.get('success'):
            source.refund(amount, reference=psp_reference)
            revoke_fulfillment = refund.status == REFUND.PENDING_WITH_REVOCATION
            refund.set_status(REFUND.PAYMENT_REFUNDED)
            refund.complete(revoke_fulfillment)
            event_type, __ = PaymentEventType.objects.get_or_create(name=PaymentEventTypeName.REFUNDED)
            PaymentEvent.objects.create(
                event_type=event_type,
                order=order,
                amount=amount,
                reference=psp_reference,
                processor_name=self.NAME
            )
        else:
            raise GatewayError(
                'Failed to issue Adyen credit for order [{order_number}].'.format(
                    order_number=order.number
                )
            )

    def issue_credit(self, source, amount, currency):
        order = source.order

        response = requests.post(
            urljoin(self.configuration.payment_api_url, 'cancelOrRefund'),
            auth=(self.configuration.web_service_username, self.configuration.web_service_password),
            headers={
                'Content-Type': 'application/json'
            },
            json={
                'merchantAccount': self.configuration.merchant_account_code,
                'originalReference': source.reference,
                'reference': order.number
            }
        )

        adyen_response = response.json()

        try:
            if response.status_code == requests.codes.ok:
                self.record_processor_response(
                    response.json(),
                    transaction_id=adyen_response['pspReference'],
                    basket=order.basket
                )
                if adyen_response['response'] != '[cancelOrRefund-received]':
                    raise GatewayError
            else:
                raise GatewayError
        except GatewayError:
            msg = 'An error occurred while attempting to issue a credit (via Adyen) for order [{}].'.format(
                order.number
            )
            logger.exception(msg)
            raise GatewayError(msg)

        return False


def _get_shopper_data(first_name='', last_name='', email='', billing_address='',
                      city='', state='', postal_code='', country='', ip=''):
    shopper_data = {}
    shopper_data.update(_get_shopper_name(first_name, last_name))
    shopper_data.update(_get_shopper_email(email))
    shopper_data.update(_get_shopper_billing_address(billing_address, city, state, postal_code, country))
    shopper_data.update(_get_shopper_ip(ip))
    return shopper_data


def _get_shopper_name(first_name, last_name):
    shopper_name = {}
    if first_name or last_name:
        shopper_name['shopper_name'] = name = {}
        if first_name:
            name['firstName'] = first_name
        if last_name:
            name['lastName'] = last_name
    return shopper_name


def _get_shopper_email(email):
    shopper_email = {}
    if email:
        shopper_email['shopperEmail'] = email
    return shopper_email


def _get_shopper_billing_address(billing_address, city, state, postal_code, country):
    shopper_billing_address = {}
    if billing_address or city or state or postal_code or country:
        shopper_billing_address['billingAddress'] = address = {}
        if billing_address:
            try:
                house_number, street = billing_address.split(' ', 1)
                address['houseNumberOrName'] = house_number
                address['street'] = street
            except ValueError:
                return {}
        if city:
            address['city'] = city
        if state:
            address['stateOrProvince'] = state
        if postal_code:
            address['postalCode'] = postal_code
        if country:
            address['country'] = country
    return shopper_billing_address


def _get_shopper_ip(ip):
    shopper_ip = {}
    if ip:
        shopper_ip['shopperIP'] = ip
    return shopper_ip