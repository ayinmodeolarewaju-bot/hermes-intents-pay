// Intents Pay desktop pane. Loaded uncompiled by Hermes Desktop.
// Imports stay on the plugin SDK and React. No network calls except ctx.rest
// into this plugin's own backend.

import { useEffect, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

var CURRENCIES = ['USDC', 'USDT', 'NEAR']
var CHAINS = ['arb', 'eth', 'base', 'sol', 'near', 'op', 'bsc', 'pol']

function fieldStyle() {
  return {
    width: '100%',
    boxSizing: 'border-box',
    border: '1px solid var(--ui-border, rgba(127,127,127,0.35))',
    background: 'transparent',
    color: 'inherit',
    borderRadius: '6px',
    padding: '6px 8px',
    font: 'inherit'
  }
}

function Button(props) {
  return jsx('button', {
    type: 'button',
    disabled: props.disabled,
    onClick: props.onClick,
    style: {
      border: '1px solid var(--ui-border, rgba(127,127,127,0.45))',
      background: props.primary ? 'var(--ui-accent, #3d7eff)' : 'transparent',
      color: props.primary ? 'white' : 'inherit',
      borderRadius: '6px',
      padding: '6px 10px',
      cursor: props.disabled ? 'default' : 'pointer',
      font: 'inherit'
    },
    children: props.children
  })
}

function Label(props) {
  return jsxs('label', {
    style: { display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '12px' },
    children: [
      jsx('span', { style: { opacity: 0.7 }, children: props.title }),
      props.children
    ]
  })
}

function IntentsPane(props) {
  var ctx = props.ctx
  var state = useState('10')
  var amount = state[0]
  var setAmount = state[1]
  var currencyState = useState('USDC')
  var currency = currencyState[0]
  var setCurrency = currencyState[1]
  var recipientState = useState('')
  var recipient = recipientState[0]
  var setRecipient = recipientState[1]
  var chainState = useState('arb')
  var chain = chainState[0]
  var setChain = chainState[1]
  var payState = useState('USDC')
  var payFrom = payState[0]
  var setPayFrom = payState[1]
  var memoState = useState('')
  var memo = memoState[0]
  var setMemo = memoState[1]
  var busyState = useState(false)
  var busy = busyState[0]
  var setBusy = busyState[1]
  var resultState = useState(null)
  var result = resultState[0]
  var setResult = resultState[1]
  var errorState = useState('')
  var error = errorState[0]
  var setError = errorState[1]
  var refundState = useState('')
  var refundTo = refundState[0]
  var setRefundTo = refundState[1]
  var agreeState = useState(false)
  var agreed = agreeState[0]
  var setAgreed = agreeState[1]
  var chainsState = useState(CHAINS)
  var chains = chainsState[0]
  var setChains = chainsState[1]

  useEffect(function () {
    var cancelled = false
    ctx.rest('/tokens').then(function (body) {
      if (!cancelled && body && body.chains && body.chains.length) setChains(body.chains)
    }).catch(function () {})
    return function () { cancelled = true }
  }, [ctx])

  function payload(extra) {
    var body = {
      amount: amount,
      currency: currency,
      recipient: recipient,
      origin_chain: chain,
      pay_from: payFrom,
      memo: memo,
      dry: true
    }
    if (extra) {
      Object.keys(extra).forEach(function (key) { body[key] = extra[key] })
    }
    return body
  }

  function run(path, body) {
    setBusy(true)
    setError('')
    return ctx.rest(path, { method: 'POST', body: body }).then(function (response) {
      setResult(response)
      if (response && response.ok === false) setError(response.error || 'Request failed')
      return response
    }).catch(function (err) {
      setError(err && err.message ? err.message : 'The Intents Pay backend is not enabled.')
    }).then(function (response) {
      setBusy(false)
      return response
    })
  }

  function dryQuote() {
    if (!recipient.trim()) {
      setError('Enter the NEAR recipient. There is no default payee.')
      return
    }
    setAgreed(false)
    run('/quote', payload({ dry: true }))
  }

  function prepareLive() {
    if (!recipient.trim()) {
      setError('Enter the NEAR recipient. There is no default payee.')
      return
    }
    if (!agreed) {
      setError('Check the box to confirm you want a deposit address. No funds are sent.')
      return
    }
    if (!refundTo.trim()) {
      setError('Enter the payer refund address on the origin chain.')
      return
    }
    run('/quote', payload({ dry: false, refund_to: refundTo.trim(), confirm: false }))
  }

  function createDeposit() {
    if (!result || !result.confirmation_token) {
      setError('Request a preview first.')
      return
    }
    run('/quote', payload({
      dry: false,
      refund_to: refundTo.trim(),
      confirm: true,
      confirmation_token: result.confirmation_token
    }))
  }

  var summary = result && result.summary ? result.summary : ''
  var needsConfirm = result && result.status === 'confirmation_required'

  return jsxs('div', {
    style: {
      height: '100%',
      overflow: 'auto',
      padding: '12px',
      display: 'flex',
      flexDirection: 'column',
      gap: '10px',
      fontSize: '13px',
      lineHeight: 1.4
    },
    children: [
      jsx('div', {
        style: { fontWeight: 650 },
        children: 'Intents Pay'
      }),
      jsx('div', {
        style: { opacity: 0.7, fontSize: '12px' },
        children: 'NEAR Intents quotes. Dry by default. This pane never sends funds.'
      }),
      jsxs('div', {
        style: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' },
        children: [
          jsx(Label, {
            title: 'Amount',
            children: jsx('input', {
              value: amount,
              onChange: function (event) { setAmount(event.target.value) },
              style: fieldStyle()
            })
          }),
          jsx(Label, {
            title: 'Receive',
            children: jsx('select', {
              value: currency,
              onChange: function (event) { setCurrency(event.target.value) },
              style: fieldStyle(),
              children: CURRENCIES.map(function (item) {
                return jsx('option', { value: item, children: item }, item)
              })
            })
          }),
          jsx(Label, {
            title: 'Pay from chain',
            children: jsx('select', {
              value: chain,
              onChange: function (event) { setChain(event.target.value) },
              style: fieldStyle(),
              children: chains.map(function (item) {
                return jsx('option', { value: item, children: item }, item)
              })
            })
          }),
          jsx(Label, {
            title: 'Pay with',
            children: jsx('input', {
              value: payFrom,
              onChange: function (event) { setPayFrom(event.target.value) },
              style: fieldStyle()
            })
          })
        ]
      }),
      jsx(Label, {
        title: 'NEAR recipient',
        children: jsx('input', {
          value: recipient,
          placeholder: 'name.near (required)',
          onChange: function (event) { setRecipient(event.target.value) },
          style: fieldStyle()
        })
      }),
      jsx(Label, {
        title: 'Memo (not sent on-chain)',
        children: jsx('input', {
          value: memo,
          onChange: function (event) { setMemo(event.target.value) },
          style: fieldStyle()
        })
      }),
      jsx(Button, { primary: true, disabled: busy, onClick: dryQuote, children: busy ? 'Working…' : 'Dry quote' }),
      error ? jsx('div', { style: { color: 'var(--ui-danger, #d4534a)' }, children: error }) : null,
      summary ? jsx('pre', {
        style: {
          whiteSpace: 'pre-wrap',
          margin: 0,
          padding: '8px',
          borderRadius: '6px',
          background: 'var(--ui-surface-sunken, rgba(127,127,127,0.12))',
          fontSize: '12px'
        },
        children: summary
      }) : null,
      jsx('div', { style: { opacity: 0.7, fontSize: '12px', marginTop: '4px' }, children: 'Deposit address' }),
      jsx('label', {
        style: { display: 'flex', gap: '8px', alignItems: 'flex-start', fontSize: '12px' },
        children: jsxs('span', {
          children: [
            jsx('input', {
              type: 'checkbox',
              checked: agreed,
              onChange: function (event) { setAgreed(event.target.checked) },
              style: { marginRight: '6px' }
            }),
            'I want a deposit address. I understand Intents Pay will not send the funds.'
          ]
        })
      }),
      jsx(Label, {
        title: 'Payer refund address',
        children: jsx('input', {
          value: refundTo,
          placeholder: 'Your address on the pay-from chain',
          onChange: function (event) { setRefundTo(event.target.value) },
          style: fieldStyle()
        })
      }),
      jsxs('div', { style: { display: 'flex', gap: '8px', flexWrap: 'wrap' }, children: [
        jsx(Button, { disabled: busy, onClick: prepareLive, children: 'Preview live quote' }),
        needsConfirm ? jsx(Button, {
          primary: true,
          disabled: busy,
          onClick: createDeposit,
          children: 'Create deposit address'
        }) : null
      ] })
    ]
  })
}

export default {
  id: 'intents-pay',
  name: 'Intents Pay',
  register: function (ctx) {
    ctx.register({
      id: 'pane',
      area: 'panes',
      title: 'Intents Pay',
      data: { placement: 'right', width: '340px' },
      render: function () { return jsx(IntentsPane, { ctx: ctx }) }
    })
  }
}
