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
                successful_payment = $('#receipt-container').data('successful-payment');
            if(order_id && successful_payment){
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
