// Starts Swagger UI on the documentation page.
//
// A static file rather than an inline script: the Content-Security-Policy allows `self`
// and nothing else, and a nonce cannot work on a site whose pages are cached whole. The
// schema URL travels in a data attribute for the same reason — nothing here may be
// interpolated into JavaScript by the template.
(function () {
    "use strict";

    var container = document.getElementById("swagger-ui");
    if (!container || typeof SwaggerUIBundle === "undefined") {
        return;
    }

    SwaggerUIBundle({
        url: container.dataset.schemaUrl,
        dom_id: "#swagger-ui",
        presets: [SwaggerUIBundle.presets.apis],
        // BaseLayout, so the standalone preset — and the topbar asking for another
        // schema URL — is never loaded. There is one API here and one document for it.
        layout: "BaseLayout",
        deepLinking: true,
        docExpansion: "list",
        defaultModelsExpandDepth: 0,
        displayRequestDuration: true,
        // The API answers GET and nothing else, so no other verb gets a button.
        supportedSubmitMethods: ["get"],
        tryItOutEnabled: true
    });
})();
