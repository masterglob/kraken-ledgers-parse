# kraken-ledgers-parse
Parse Kraken ledgers export to ease taxes declarations.
It is intended to fit French tax declaration rules (2022), but may be used in more general way to get a summary of operations.

## Configure
- Install python (>= 3.8)
- Create a sub-folder `files` and create ledgers and deposits entries. (see below)

### Ledgers
This file is the Kraken export and conains all operations on this platform
- In your Kraken account, export a LEDGERS csv file. this exports MUST start with the account creation and must contains all operations since.
- Save this files as `files/ledgers<XXXX>.csv`, replacing <XXXX> by the current year. (e.g. `files/ledgers2022.csv`). It is expected that the year is ended, so that all transactions are declared

### Deposits
This file intends at providing all (non-EURO) deposits on the account. It is mandatory so that the parser can evaluate the value of each asset in the wallet.
- Create a comma-separatedCSV file `files/deposits<XXXX>.csv` (same rule for <XXXX>). Set the first line as:
```"time","asset","amount","costEur","reason","note"```.
- Enter each non-EUR deposits in a separate line with:
  - Each field must be sourrounded by double quotes (e.g.`"SOL"`). Actually, float aomunt do not //need// this, but this ensures constency and avoid errors
  - `time` must be prior matching ledger entry (Adive: use 1 sec priori to entry, to keep operations close). The expected format is `"YYYY-MM-DD hh:mm:ss"`, including zeros.
  - `asset` must be prior matching ledger entry (Adive: use 1 sec priori to entry, to keep operations close)
  - `amount` is the amount (for the given `asset`) of the deposit, as float number (using "." as decimal separator).
  - `costEur` is the mean value in EURO of the initial cost of this amount. For an airdrop, or a coin fork, this should be "0" 
  - `reason` is a short text field precising the type of the deposit. This is not currently used by the tool, but only intended for help.
  - `note` is a more detailled field precising the type of the deposit. This is not currently used by the tool, but only intended for help.

Example :
```
"time","asset","amount","costEur","reason","note"
"2022-05-28 22:06:00","LUNA2", "0.04592400", 0.0, "fork","LUNA => LUNA+LUNA2, implicit airdrop"
"2023-02-04 12:19:29","KAVA", "2.91921000", "3.0" ,"deposit","KAVA deposit 2.91921000"
```
Note:
- Currently, the version only considers EUR as 'fiat' asset. Thus USD (or other fiat asset) external operations will have to be registered in the `deposit` file.
- There is no need to list EUR deposits, as by definition, the buying price is constant and does not need justification

### Running
Once the ledgers and deposits entries are ready, simply execute `impots_k.py` as python 3 script.

In case of success, a text summary is displayed on the console, providing:
- A summary of all assets as follow:
`| <ASSET> :   <Amount> [Stake :<amount> ] [Deposited|Withdrawn : <Amount>]  <Mean buy value> `
  - Note that "depEUR" asset corresponds to the content of `deposits` file, and not to the total amount of injected EUROs. 

- A summary of all gains by year (Value to be declared for taxes):

```
Wallet content: (2023-04-14 00:37:15)
| >depEUR:         19.000000                          Deposited:       19.000000       -1.00
| ADA    :          0.000000  Stake:       52.277180                                   +1.85
| CTSI   :          0.000000                                                           +0.74
| TRX    :          0.000004  Stake:      310.616857                                   +0.08
| USDT   :         13.782206                          Deposited:       16.324256       +0.98
| UST    :          0.000001                          Withdrawn:      139.493197       +0.06
| XETC   :          1.693495                                                          +26.36
| XETH   :          0.085112                                                        +1945.34
| XTZ    :          0.000000  Stake:        4.287865                                   +4.21
| XXBT   :          0.000007                                                       +34242.38
| XXDG   :         99.999905                                                           +0.17
| XXRP   :          0.000000                                                           +0.39
| ZEUR   :         11.888800                          Deposited:     2644.710000       +1.00
| ZRX    :          0.000028                                                           +0.61
Year 2020 : Gains =    +0 EUR
Year 2021 : Gains =   +27 EUR
Year 2022 : Gains =   -59 EUR
Year 2023 : Gains =   +18 EUR
Terminated successfully

```
