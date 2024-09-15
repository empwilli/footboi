# footboi

Generic utility to poll financial transaction data from bank interfaces and generate events thereof.

## Description

footboi is a small plugable utility that fetches financial data from bank interfaces and 
generates events if there are new transaction. footboi currently implements connectors for FINTS, but
you can easily extend it for other service providers, as well.

To tell old from new statements, footboi relies on a mongodb as background storage.

**NOTE**: footboi will call financial APIs at your bank service providers. Utmost care has been taken
that data is only read, but please read and understand the underlying code. Still, this is experimental
software for developed for my own needs, so use at your own risk!

## Configuration

```toml
[accounts]

[account.bank1]
user_id = "1234"
bank_id = "7654"
# either use the pin directly
pin = "1234"
# ... or a pin command
pin_cmd = "pass bank1/1234"
endpoint = "https://banking-by1.s-fints-pt-by.de/fints30"
```
