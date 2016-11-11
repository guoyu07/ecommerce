/**
 * Basket page scripts.
 **/

define([
        'jquery',
        'jquery-url'
    ],
    function ($
    ) {
        'use strict';

        var onReady = function() {
            var order_id = $.url('?order_number') || null,
                data_payment_successful = $('#receipt-container').data('payment-successful');
            if(order_id && data_payment_successful){
                trackPurchase(order_id);
            }
        },
        trackPurchase = function(order_id) {
            var el = $('#receipt-container');
            window.analytics.track('Completed Purchase', {
                orderId: order_id,
                total: el.data('total-amount'),
                currency: el.data('currency')
            });
        };

        return {
            onReady: onReady,
            trackPurchase: trackPurchase
        };
    }
);
