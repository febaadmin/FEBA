# NATS 2.15 — messagerie temps réel de plugNmeet (chat, tableau blanc,
# sondages). Repris du modèle officiel plugNmeet-install ; généré par
# scripts/plugnmeet_setup.sh (clés publiques uniquement ici).
websocket {
    port: 8222
    no_tls: true
}

jetstream: {
    store_dir: /data/jetstream
}

accounts {
    SYS: {
        exports: [
            {
                stream: "$SYS.ACCOUNT.PNM.>",
                accounts: [PNM]
            }
        ]
    }
    PNM: {
        jetstream: enabled
        imports: [
            {
                stream: {
                    account: SYS, subject: "$SYS.ACCOUNT.PNM.>"
                }
            }
        ]
        users: [
            {
                nkey: ${NATS_NKEY_PUBLIC_KEY}
            }
        ]
    }
}

system_account: SYS

authorization {
    timeout: 5
    auth_callout {
        issuer: ${NATS_CALLOUT_PUBLIC_KEY}
        auth_users: [ ${NATS_NKEY_PUBLIC_KEY} ]
        account: PNM
        xkey: ${NATS_XKEY_PUBLIC_KEY}
    }
}
