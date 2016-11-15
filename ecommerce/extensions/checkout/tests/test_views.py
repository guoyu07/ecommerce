import json
from decimal import Decimal

import ddt
import httpretty
from django.core.urlresolvers import reverse
from oscar.core.loading import get_model
from oscar.test import newfactories as factories

from ecommerce.coupons.tests.mixins import CourseCatalogMockMixin
from ecommerce.extensions.checkout.exceptions import BasketNotFreeError
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.refund.tests.mixins import RefundTestMixin
from ecommerce.tests.mixins import LmsApiMockMixin
from ecommerce.tests.testcases import TestCase

Order = get_model('order', 'Order')


class FreeCheckoutViewTests(TestCase):
    """ FreeCheckoutView view tests. """
    path = reverse('checkout:free-checkout')

    def setUp(self):
        super(FreeCheckoutViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)
        self.toggle_ecommerce_receipt_page(True)

    def prepare_basket(self, price):
        """ Helper function that creates a basket and adds a product with set price to it. """
        basket = factories.BasketFactory(owner=self.user, site=self.site)
        basket.add_product(factories.ProductFactory(stockrecords__price_excl_tax=price), 1)
        self.assertEqual(basket.lines.count(), 1)
        self.assertEqual(basket.total_incl_tax, Decimal(price))

    def test_empty_basket(self):
        """ Verify redirect to basket summary in case of empty basket. """
        response = self.client.get(self.path)
        expected_url = self.get_full_url(reverse('basket:summary'))
        self.assertRedirects(response, expected_url)

    def test_non_free_basket(self):
        """ Verify an exception is raised when the URL is being accessed to with a non-free basket. """
        self.prepare_basket(10)

        with self.assertRaises(BasketNotFreeError):
            self.client.get(self.path)

    @httpretty.activate
    def test_successful_redirect(self):
        """ Verify redirect to the receipt page. """
        self.prepare_basket(0)
        self.assertEqual(Order.objects.count(), 0)

        response = self.client.get(self.path)
        self.assertEqual(Order.objects.count(), 1)

        order = Order.objects.first()
        expected_url = get_receipt_page_url(
            order_number=order.number,
            site_configuration=order.site.siteconfiguration
        )
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)

    @httpretty.activate
    def test_redirect_to_lms_receipt(self):
        """ Verify that disabling the otto_receipt_page switch redirects to the LMS receipt page. """
        self.toggle_ecommerce_receipt_page(False)
        self.prepare_basket(0)
        self.assertEqual(Order.objects.count(), 0)
        receipt_page = self.site.siteconfiguration.build_lms_url('/commerce/checkout/receipt')

        response = self.client.get(self.path)
        self.assertEqual(Order.objects.count(), 1)

        expected_url = '{}?orderNum={}'.format(receipt_page, Order.objects.first().number)
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)


class CancelCheckoutViewTests(TestCase):
    """ CancelCheckoutView view tests. """

    path = reverse('checkout:cancel-checkout')

    def setUp(self):
        super(CancelCheckoutViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

    @httpretty.activate
    def test_get_returns_payment_support_email_in_context(self):
        """
        Verify that after receiving a GET response, the view returns a payment support email in its context.
        """
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['payment_support_email'], self.request.site.siteconfiguration.payment_support_email
        )

    @httpretty.activate
    def test_post_returns_payment_support_email_in_context(self):
        """
        Verify that after receiving a POST response, the view returns a payment support email in its context.
        """
        post_data = {'decision': 'CANCEL', 'reason_code': '200', 'signed_field_names': 'dummy'}
        response = self.client.post(self.path, data=post_data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['payment_support_email'], self.request.site.siteconfiguration.payment_support_email
        )


class CheckoutErrorViewTests(TestCase):
    """ CheckoutErrorView view tests. """

    path = reverse('checkout:error')

    def setUp(self):
        super(CheckoutErrorViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

    @httpretty.activate
    def test_get_returns_payment_support_email_in_context(self):
        """
        Verify that after receiving a GET response, the view returns a payment support email in its context.
        """
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['payment_support_email'], self.request.site.siteconfiguration.payment_support_email
        )

    @httpretty.activate
    def test_post_returns_payment_support_email_in_context(self):
        """
        Verify that after receiving a POST response, the view returns a payment support email in its context.
        """
        post_data = {'decision': 'CANCEL', 'reason_code': '200', 'signed_field_names': 'dummy'}
        response = self.client.post(self.path, data=post_data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['payment_support_email'], self.request.site.siteconfiguration.payment_support_email
        )


@ddt.ddt
class ReceiptResponseViewTests(CourseCatalogMockMixin, LmsApiMockMixin, RefundTestMixin, TestCase):
    """
    Tests for the receipt view.
    """

    path = reverse('checkout:receipt')

    def setUp(self):
        super(ReceiptResponseViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

    def _get_cybersource_response(self, decision):
        """
        Helper function used in tests to make a post request with CyberSource response.

        Arguments:
            decision (str): Decision returned by CyberSource.

        Returns:
            TemplateResponse: Response of the POST Request to the ReceiptView.
        """
        return self.client.post(
            self.path,
            params={'basket_id': 1},
            data={'decision': decision, 'reason_code': '200', 'signed_field_names': 'dummy'}
        )

    def _visit_receipt_page_with_another_user(self, order, user):
        """
        Helper function for logging in with another user and going to the Receipt Page.

        Arguments:
            order (Order): Order for which the Receipt Page should be opened.
            user (User): User that's logging in.

        Returns:
            response (Response): Response object that's returned by a ReceiptResponseView
        """
        self.client.logout()
        self.client.login(username=user.username, password=self.password)
        return self.client.get('{path}?order_number={order_number}'.format(
            order_number=order.number,
            path=self.path
        ))

    def test_login_required_post_request(self):
        """ The view should redirect to the login page if the user is not logged in. """
        self.client.logout()
        response = self.client.post(self.path)
        self.assertEqual(response.status_code, 302)

    def test_login_required_get_request(self):
        """ The view should redirect to the login page if the user is not logged in. """
        self.client.logout()
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 302)

    def test_get_receipt_for_nonexisting_order(self):
        """ The view should return 404 status if the Order is not found. """
        order_number = 'ABC123'
        response = self.client.get('{path}?order_number={order_number}'.format(
            order_number=order_number,
            path=self.path
        ))
        self.assertEqual(response.status_code, 404)

    @httpretty.activate
    def test_get_receipt_for_existing_order(self):
        """
        Staff user and Order owner should be able to see the Receipt Page.
        All other users should get the 404 status.
        """
        staff_user = self.create_user(is_staff=True)
        other_user = self.create_user()

        order = self.create_order()
        self.mock_verification_status_api(
            self.request,
            self.user,
            status=200,
            is_verified=False
        )
        response = self.client.get('{path}?order_number={order_number}'.format(
            order_number=order.number,
            path=self.path
        ))
        context_data = {
            'name': '{} {}'.format(order.user.first_name, order.user.last_name),
            'page_title': 'Receipt',
            'providers': []
        }
        self.assertEqual(response.status_code, 200)
        self.assertDictContainsSubset(context_data, response.context_data)

        self.mock_verification_status_api(
            self.request,
            staff_user,
            status=200,
            is_verified=False
        )
        response = self._visit_receipt_page_with_another_user(order, staff_user)
        self.assertEqual(response.status_code, 200)
        self.assertDictContainsSubset(context_data, response.context_data)

        self.mock_verification_status_api(
            self.request,
            other_user,
            status=200,
            is_verified=False
        )
        response = self._visit_receipt_page_with_another_user(order, other_user)
        context_data = {'page_title': 'Order not found'}
        self.assertEqual(response.status_code, 404)
        self.assertDictContainsSubset(context_data, response.context_data)

    @httpretty.activate
    def test_order_data_for_credit_seat(self):
        """ Ensure that the context is updated with Order data. """
        order = self.create_order(credit=True)
        seat = order.lines.first().product
        body = {'display_name': 'Hogwarts'}

        httpretty.register_uri(
            httpretty.GET,
            self.site.siteconfiguration.build_lms_url(
                'api/credit/v1/providers/{credit_provider}/'.format(credit_provider=seat.attr.credit_provider)
            ),
            body=json.dumps(body),
            content_type="application/json"
        )

        self.mock_verification_status_api(
            self.request,
            self.user,
            status=200,
            is_verified=True
        )

        response = self.client.get('{path}?order_number={order_number}'.format(
            order_number=order.number,
            path=self.path
        ))

        body['course_key'] = seat.attr.course_key
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context_data['providers'][0], body)
        self.assertEqual(len(response.context_data['providers']), 1)
