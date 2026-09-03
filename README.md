# Sainsbury's Groceries for Home Assistant

An unofficial Home Assistant integration for a Sainsbury's Groceries Online
account. It exposes the current basket, latest order and reserved delivery or
collection slot, and provides actions for catalogue search and basket changes.

This project is not affiliated with, endorsed by or supported by J Sainsbury plc.
It uses the unofficial
[`pysainsburys`](https://github.com/pantherale0/pysainsburys) library and may
stop working if Sainsbury's changes its private APIs.

## Installation

### HACS

1. Open HACS in Home Assistant.
2. Add `https://github.com/pantherale0/ha-sainsburys` as a custom integration
   repository.
3. Search for **Sainsbury's Groceries** and install it.
4. Restart Home Assistant.

### Manual

1. Copy `custom_components/sainsburys` into the `custom_components` directory
   in your Home Assistant configuration directory.
2. Restart Home Assistant.

## Configuration

1. Open **Settings → Devices & services**.
2. Select **Add integration**.
3. Search for **Sainsbury's Groceries**.
4. Enter the email address and password for your Sainsbury's account.
5. If requested, enter the one-time verification code sent by Sainsbury's.

Home Assistant stores the resulting session tokens and cookies. It does not
store the account password. A Sainsbury's account with Groceries Online access
is required. Each account can be configured once; multiple different accounts
are supported.

Use **Reconfigure** from the integration menu to sign in with updated
credentials. If a session expires, Home Assistant automatically starts a
reauthentication flow.

## Data provided

The integration creates one service device per Sainsbury's account.

Sensors:

- Basket total, subtotal, savings and Nectar savings
- Basket item count, with basket lines in its attributes
- Latest order status and total
- Reserved slot start and end
- Order amend cutoff
- Delivery pass expiry (diagnostic, disabled by default)

Binary sensors:

- Minimum spend met
- Order amendable
- Slot reserved
- Nectar linked (diagnostic, disabled by default)

## Actions

When only one account is configured, `config_entry_id` may be omitted. Select
it when multiple accounts are configured.

### Search products

`sainsburys.search_products` accepts `query`, `page_number` and `page_size`.
It returns `products` and pagination `controls`. Product entries include the
product UID, name, prices, availability, image URL, reviews and nutrition data
when Sainsbury's supplies them.

```yaml
action: sainsburys.search_products
data:
  query: semi skimmed milk
  page_size: 10
response_variable: search
```

Use `{{ search.products[0].product_uid }}` to pass a selected result to a
basket action. Search can return multiple products, so basket actions
deliberately do not accept a product name.

### Get a product

`sainsburys.get_product` returns details for one `product_uid`.

```yaml
action: sainsburys.get_product
data:
  product_uid: "3236048"
response_variable: product
```

### Change the basket

- `sainsburys.add_basket_item`: requires `product_uid`; `quantity` defaults to
  one.
- `sainsburys.set_basket_item`: requires `product_uid` and the absolute
  `quantity`. Zero removes the line.
- `sainsburys.remove_basket_item`: requires `product_uid`.
- `sainsburys.clear_basket`: removes all basket lines.

Example automation:

```yaml
alias: Add milk to the grocery basket
triggers:
  - trigger: state
    entity_id: input_button.add_milk
actions:
  - action: sainsburys.search_products
    data:
      query: Sainsbury's semi skimmed milk 2.27L
      page_size: 1
    response_variable: search
  - condition: template
    value_template: "{{ search.products | count > 0 }}"
  - action: sainsburys.add_basket_item
    data:
      product_uid: "{{ search.products[0].product_uid }}"
      quantity: 1
```

All basket actions request an immediate account refresh after succeeding.
An empty product search is successful and returns an empty `products` list.

## Data updates

Account data is polled every 15 minutes. Basket actions trigger an immediate
refresh. Product search and product detail requests run only when their actions
are called and do not alter coordinator data.

If Sainsbury's is temporarily unavailable, entities become unavailable and
Home Assistant retries on the next update. Authentication failures prompt for
reauthentication.

## Known limitations

- This is an unofficial cloud integration using private Sainsbury's endpoints.
- Checkout, payment and slot booking are not supported.
- Favourites and Nectar offer unlocking are not exposed.
- Product search is an action response, not a browsable Home Assistant entity.
- Catch-weight products may require information not exposed by the actions.
- Sainsbury's may rate-limit or block automated access.

## Troubleshooting

### Invalid email, password or verification code

Confirm the same credentials work on the Sainsbury's Groceries website. Start
the flow again if the verification code expired.

### Entities are unavailable

Check the Home Assistant logs for `sainsburys` or `pysainsburys`. Temporary
Sainsbury's outages recover automatically. Use **Reconfigure** if the account
credentials changed.

### Basket action says the item is invalid

Run `sainsburys.search_products` and use an exact `product_uid`. If the same
product appears on multiple basket lines, resolve the duplicate in the
Sainsbury's website or app first.

Diagnostics are available from the integration's device page. The diagnostics
exclude credentials, account identifiers, contact details and basket line
contents.

## Removal

1. Open **Settings → Devices & services**.
2. Open **Sainsbury's Groceries**.
3. Select the menu for the account and choose **Delete**.
4. Remove the integration from HACS or delete
   `custom_components/sainsburys` if it is no longer needed.

Removing the integration does not delete the Sainsbury's account or change its
basket.

## Development

Run `scripts/setup`, then use:

```bash
scripts/lint
pytest
```

The integration follows Home Assistant's Integration Quality Scale rules as
tracked in `custom_components/sainsburys/quality_scale.yaml`.
