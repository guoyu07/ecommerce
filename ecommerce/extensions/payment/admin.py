from pprint import pformat

from django.utils.html import format_html
from oscar.apps.payment.admin import *  # noqa pylint: disable=wildcard-import,unused-wildcard-import,wrong-import-position
from oscar.core.loading import get_model
from solo.admin import SingletonModelAdmin

PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')
PaypalProcessorConfiguration = get_model('payment', 'PaypalProcessorConfiguration')

admin.site.unregister(Source)


@admin.register(Source)
class SourceAdminExtended(SourceAdmin):
    raw_id_fields = ('order',)
    show_full_result_count = False


@admin.register(PaymentProcessorResponse)
class PaymentProcessorResponseAdmin(admin.ModelAdmin):
    list_filter = ('processor_name',)
    search_fields = ('id', 'processor_name', 'transaction_id',)
    list_display = ('id', 'processor_name', 'transaction_id', 'basket', 'created')
    fields = ('processor_name', 'transaction_id', 'basket', 'formatted_response')
    readonly_fields = ('processor_name', 'transaction_id', 'basket', 'formatted_response')
    show_full_result_count = False

    def formatted_response(self, obj):
        pretty_response = pformat(obj.response)

        # Use format_html() to escape user-provided inputs, avoiding an XSS vulnerability.
        return format_html('<br><br><pre>{}</pre>', pretty_response)

    formatted_response.allow_tags = True


admin.site.register(PaypalProcessorConfiguration, SingletonModelAdmin)
