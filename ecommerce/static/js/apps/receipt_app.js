require([
        'jquery',
        'pages/receipt_page'
    ],
    function ($,
              ReceiptPage) {
        'use strict';

        $(document).ready(ReceiptPage.onReady);
    }
);
