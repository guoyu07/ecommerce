/**
 * Basket page scripts.
 **/

define([
        'jquery'
    ],
    function ($
    ) {
        'use strict';

        var el = $('#receipt-container'),
        onReady = function() {
            var order_id = el.data('order-id'),
                data_fire_tracking_events = el.data('fire-tracking-events');
            if(order_id && data_fire_tracking_events){
                trackPurchase(order_id);
            }
        },
        trackPurchase = function(order_id) {
            window.analytics.track('Completed Purchase', {
                orderId: order_id,
                total: el.data('total-amount'),
                currency: el.data('currency')
            });
        };

        $(document).ready(onReady);
    }
);
