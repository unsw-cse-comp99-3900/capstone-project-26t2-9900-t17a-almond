vnc_display_setup_auth(VncDisplay *vs,

                       bool password,

                       bool sasl,

                       bool tls,

                       bool x509)

{

    /*

     * We have a choice of 3 authentication options

     *

     *   1. none

     *   2. vnc

     *   3. sasl

     *

     * The channel can be run in 2 modes

     *

     *   1. clear

     *   2. tls

     *

     * And TLS can use 2 types of credentials

     *

     *   1. anon

     *   2. x509

     *

     * We thus have 9 possible logical combinations

     *

     *   1. clear + none

     *   2. clear + vnc

     *   3. clear + sasl

     *   4. tls + anon + none

     *   5. tls + anon + vnc

     *   6. tls + anon + sasl

     *   7. tls + x509 + none

     *   8. tls + x509 + vnc

     *   9. tls + x509 + sasl

     *

     * These need to be mapped into the VNC auth schemes

     * in an appropriate manner. In regular VNC, all the

     * TLS options get mapped into VNC_AUTH_VENCRYPT

     * sub-auth types.

     */

    if (password) {

        if (tls) {

            vs->auth = VNC_AUTH_VENCRYPT;

            if (x509) {

                VNC_DEBUG("Initializing VNC server with x509 password auth\n");

                vs->subauth = VNC_AUTH_VENCRYPT_X509VNC;

            } else {

                VNC_DEBUG("Initializing VNC server with TLS password auth\n");

                vs->subauth = VNC_AUTH_VENCRYPT_TLSVNC;

            }

        } else {

            VNC_DEBUG("Initializing VNC server with password auth\n");

            vs->auth = VNC_AUTH_VNC;

            vs->subauth = VNC_AUTH_INVALID;

        }

    } else if (sasl) {

        if (tls) {

            vs->auth = VNC_AUTH_VENCRYPT;

            if (x509) {

                VNC_DEBUG("Initializing VNC server with x509 SASL auth\n");

                vs->subauth = VNC_AUTH_VENCRYPT_X509SASL;

            } else {

                VNC_DEBUG("Initializing VNC server with TLS SASL auth\n");

                vs->subauth = VNC_AUTH_VENCRYPT_TLSSASL;

            }

        } else {

            VNC_DEBUG("Initializing VNC server with SASL auth\n");

            vs->auth = VNC_AUTH_SASL;

            vs->subauth = VNC_AUTH_INVALID;

        }

    } else {

        if (tls) {

            vs->auth = VNC_AUTH_VENCRYPT;

            if (x509) {

                VNC_DEBUG("Initializing VNC server with x509 no auth\n");

                vs->subauth = VNC_AUTH_VENCRYPT_X509NONE;

            } else {

                VNC_DEBUG("Initializing VNC server with TLS no auth\n");

                vs->subauth = VNC_AUTH_VENCRYPT_TLSNONE;

            }

        } else {

            VNC_DEBUG("Initializing VNC server with no auth\n");

            vs->auth = VNC_AUTH_NONE;

            vs->subauth = VNC_AUTH_INVALID;

        }

    }

}
