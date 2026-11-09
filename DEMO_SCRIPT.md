# Demo script (about 80 seconds)

Post on X, under 90 seconds, and tag @NousResearch. Show the plugin working. Do not send funds and do not finish a live deposit-address quote on camera unless you mean to pay.

Record a terminal with Hermes Agent and Intents Pay already enabled (`hermes plugins enable intents-pay`). Default recipient: `purefile1686.near`.

| Time | On screen | Say |
| --- | --- | --- |
| 0–6s | `hermes plugins list --plain --no-bundled` with `intents-pay` enabled | "Intents Pay is a Hermes plugin for NEAR Intents. It quotes a payment onto a NEAR account from whatever chain the payer actually holds." |
| 6–22s | `hermes intents-pay quote --amount 25 --currency USDC --from-chain arb --recipient purefile1686.near` | "Twenty-five USDC to purefile1686.near, paid from USDC on Arbitrum. This is a dry quote: Hermes shows what the payer would send, the 1-Click signature verifies, and there is no deposit address." |
| 22–36s | Point at "Payer sends about…", "Recipient gets: 25.0 USDC", and "1-Click signature: verified." | "The recipient gets the invoiced amount. The extra is the route, not a fee this plugin adds. The signature is checked locally with 1-Click's published key." |
| 36–50s | `hermes intents-pay quote --amount 10 --currency USDT --from-chain arb --from-token USDT --recipient purefile1686.near` | "Same invoice idea from Tether. On Arbitrum, 1-Click lists it as USDT0, and the plugin matches that." |
| 50–64s | `hermes intents-pay quote --amount 1 --from-chain arb --live --refund-to 0xYOUR_ADDRESS` and stop when the confirmation token prints | "Asking for a real deposit address does not run on the first call. Hermes returns the dry preview and a one-time token. It still has not moved any funds." |
| 64–76s | `hermes intents-pay status` showing the dry invoice and `deposit_address: null` | "The invoice is saved. Status knows there is nothing to track on-chain until a confirmed live quote exists." |
| 76–82s | Hold on the safety lines in the card | "No seed phrase, no signing key, no broadcast. The payer sends from their own wallet, and only after they confirm." |

If Hermes Desktop is open, cut the last four seconds to the Intents Pay pane: type 25 USDC, Arbitrum, `purefile1686.near`, click **Dry quote**, and show the same card. Leave **Create deposit address** unclicked.

Do not paste a seed phrase, do not pass `--confirm-token` on camera, and do not show a funded wallet.
