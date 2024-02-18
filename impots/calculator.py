'''
Created on 16 avr. 2023

@author: MAO
'''
import sys

from datetime import datetime

from read_csv import CSV_File, Transaction,CalcExcept, AValue, DEBUG, BalanceError, DEPOSIT_EUR_FEE, actualAsset, Ledger_Kraken

from journal import Journal
from known_coins import FIAT_EUR


# Set DBG_ASSET to None or any asset name (e.g. "SOL")
DBG_ASSET = None
#DBG_ASSET="MATIC"

# Set DBG_TXID to None or any tid name (e.g. "LS5Q2D-WJ7WC-73LBHD")
DBG_TXID = None

def isEURO(asset):return asset == FIAT_EUR

def niceFloat(f):
    if abs(f) < 1e-4: return f"{f:.2e}"
    if abs(f) < 10: return f"{f:.3f}" 
    return f"{f:.0f}" 
class CGain:
    def __init__(self, trans, gain, tVal, deposit, wVal, fees =0):
        self.trans= trans
        self.gain= gain
        self.tVal= tVal # Transaction valuation
        self.wVal= wVal # Wallet total valuation
        self.deposit= deposit
        self.fees= fees
    
class FValue(object): # A value associated with a mean FIAT value
    def __init__(self, asset):
        if (asset == "ETH2"):
                assert(False)
        asset=actualAsset(asset)
        self.amount = 0.0
        self.asset=asset
        self.meanEurValue = 0.0
    def __str__(self):
        return f"FV({self.amount} {self.asset} @{self.meanEurValue})"
    def valuationEUR(self):
        if self.asset == DEPOSIT_EUR_FEE :
            self.meanEurValue = -1.0
        if self.asset == FIAT_EUR : self.meanEurValue =1.0
        return self.amount*self.meanEurValue
    
    def buy(self, amount : float, src:AValue):
        '''
        @param src: FValue
        '''
        if not (amount >= 0):  raise Exception( f"FValue.buy(amount={amount})")
        
        amountPrev = self.amount
        self.amount += amount
        
        if self.asset == src.asset: return
        if isEURO(self.asset):
            raise Exception('TODO') 
        elif isEURO(src.asset): 
            # recompute estimated value
            
            # Example: xchange 100 EUR into 1 ETH (self = ETH, src=EUR)
            totalEurValue = self.meanEurValue * amountPrev + abs( src.value)
            try: self.meanEurValue = totalEurValue / self.amount
            except: self.amount, self.meanEurValue = 0.0,0.0
            
            print (f"Buy {amount} {self.asset} with {src}, current amount={amountPrev}")
            print (f"totalEurValue={totalEurValue}, self.amount= {self.amount}")
            print (f"Current valuation={self.meanEurValue} {src.asset}/{self.asset}")
            
            return
        
        else: # None is EURO
            raise Exception('TODO') 
        
    def sell(self, amount : float, dst:AValue):
        if not (amount <= 0):  raise Exception( f"FValue.sell(amount={amount})")
        amountPrev = self.amount # meanEurValue is the buying value: not impacted
        self.amount += amount
        
        if self.amount < -1e-6:
#             print (self.currencies[v.asset])
            missing=self.amount
            self.amount -= amount
            raise CalcExcept(f"Cannot remove {amount} {self.asset} from wallet(current funds:{self.amount}: not enough funds (Missing {missing})")
        
        if dst is None: return # TODO HERE this is a withdraw/deposit?
        
        
        
        if self.asset == dst.asset:
            raise Exception('TODO') 
        
        if isEURO(self.asset):
            raise Exception('TODO') 
        elif isEURO(dst.asset): 
            # recompute estimated value
            # Example: xchange 1 ETH into 100 EUR  (self = EUR, dst=ETH)
            oldEurValue = self.meanEurValue * amountPrev
            newEurValue = self.meanEurValue * self.amount
            try: dst.meanEurValue = newEurValue / dst.amount
            except: dst.amount, dst.meanEurValue = 0.0,0.0
            
            print (f"Sell {amount} {self.asset} for {dst}, current amount={amountPrev}")
            print (f"totalEurValue=(old:{oldEurValue}, new:{newEurValue}), self.amount= {self.amount}")
            print (f"Current valuation={self.meanEurValue*self.amount} with mean price at {self.meanEurValue} {dst.asset}/{self.asset}")
            return
    
        else : # none is EURO
            raise Exception('TODO') 
        
class Wallet(object):
    def __init__(self):
        print("[II] Created a wallet")
        self.journal = Journal()
        self.currencies={} # A {asset:FValue} dict
        self.depositEUR = 0.0
        self.deposit={FIAT_EUR:0.0, DEPOSIT_EUR_FEE:0.0}  # asset:value (includes staking) 
        self.gains = []
        self.gainsByYear = {}
        self.gainTotal = 0.0
        self.lastTransactionDate = None # (date)
        self.firstTransactionDate = None # (date)
        
    def valueInEuro(self, val:AValue):
        return val.value * self.currencies[val.asset].meanEurValue
    
    def shortStatus(self):
        return f"gains:{self.gainTotal}, injected:{self.depositEUR}"
        
    def valuationDeposit(self):
        return self.deposit[DEPOSIT_EUR_FEE] *1.0 # Just used to check and log external non-EURO deposits
    def valuationEUR(self):
        return sum(c.valuationEUR() for _,c in self.currencies.items()) - self.deposit[FIAT_EUR] * 1.0
    def __swapFee(self, src:AValue, dst:AValue, gain):
        if not dst : dst = AValue(asset=src.asset, value=0.0)
        # print (f"__swapFee ({src},{dst})")
        if src.asset not in self.currencies:
            self.currencies[src.asset] = FValue(src.asset)
        if dst.asset not in self.currencies:
            self.currencies[dst.asset] = FValue(dst.asset)
        currSrc = self.currencies[src.asset]
        currDst = self.currencies[dst.asset]
        currSrc.amount += src.value
        currDst.amount += dst.value
        if gain:
            gain.fees += self.valueInEuro(src) +  self.valueInEuro(dst)
        
    def __swap(self, trans :Transaction):
        # for breakpoint:
        if trans.txid == DBG_TXID:
            _dbg=1 # print ("!Break!")
        src=trans.src
        dst=trans.dst
        reason = trans.notice
        self.lastTransactionDate = trans.date
        if self.firstTransactionDate == None :
            self.firstTransactionDate = trans.date
        assert(type(src.value) is float)
        assert(type(src.asset) is str)
        if src.value == -0.0: src.value = 0.0 # TODO remove ?
        if not dst : dst = AValue(asset=src.asset, value=0.0)
        
        # print (f"__swap ({src},{dst},{reason})")
        
        oldValuation = self.valuationEUR()
        oldDeposit = self.valuationDeposit()
        
        # Create wallets assets if required
        if src.asset not in self.currencies:
            self.currencies[src.asset] = FValue(src.asset)
        if dst.asset not in self.currencies:
            self.currencies[dst.asset] = FValue(dst.asset)
        
        if not (src.value <= 0):  raise Exception( f"Wallet.swap(src.value={src.value})")
        currSrc = self.currencies[src.asset]
        currDst = self.currencies[dst.asset]
        dstPrevAmount = currDst.amount
        currSrc.amount += src.value
        currDst.amount += dst.value
        transactionValuation = abs (currSrc.meanEurValue * src.value)
        missValueEur= abs(currSrc.meanEurValue*currSrc.amount)
        if abs(missValueEur) < -1e-6:
            missing=currDst.amount
            currSrc.amount -= dst.value
            raise CalcExcept(f"Cannot remove {src} from wallet(current funds:{currSrc.amount}: not enough funds (Missing {missing})")
        if currSrc.amount < 0:
            currSrc.amount = 0.0
        # update valuation
        if not dst.asset in self.deposit : self.deposit[dst.asset] = 0.0
        if reason == "deposit":
            self.deposit[dst.asset] += 1.0 * dst.value
            self.journal.deposit(trans, dst.asset, 1.0 * dst.value)
            # print(f"Deposited {dst} => {self.deposit[dst.asset]} ")
        elif reason == "withdrawal":
            # prev = self.deposit[dst.asset]
            self.deposit[dst.asset] += 1.0 * src.value
            self.journal.withdrawal(trans, dst.asset, 1.0 * src.value)
            # print(f"Withdrawn {dst} :{prev} => {self.deposit[dst.asset]} ")
            # Note : withdraw can be negative due to staking
            pass
        else:
            # The "src" wallet value is already up to date (only amount changed, mean value is not modified)
            # The Dst wallet mean value must be recomputed
            dstTotalValue = (currDst.meanEurValue  * dstPrevAmount) + transactionValuation
            
            if currDst.amount > 1e-8:
                currDst.meanEurValue = dstTotalValue / currDst.amount
            # print(f"Mean value for {dst} changed to {currDst.meanEurValue}")
            self.journal.transaction(trans, src.asset, dst.asset, currDst.meanEurValue)
            
        self.depositEUR = self.deposit[FIAT_EUR]
        if reason not in ["staking"]: # Avoid useless logs
            # Now, update the estimated value of wallet
            newValuation = self.valuationEUR()
            depositDelta = self.valuationDeposit() - oldDeposit
            g = newValuation- oldValuation
            gainRes = CGain(trans, g, transactionValuation, depositDelta,newValuation)
            self.gains.append(gainRes)
            self.gainTotal += gainRes.gain
            date = trans.date
            assert (type(date) == datetime)
            year = date.date().year
            assert(year > 1990)
            if year not in self.gainsByYear: self.gainsByYear[year] = 0.0
            self.gainsByYear[year] += gainRes.gain
#             print (f"Valuation :{gainRes} / deposit:{self.depositEUR} EUR")
            return gainRes
        return
        
        
    def apply(self, trans : Transaction):
        dbg=0
        if trans.src.asset == DBG_ASSET or trans.dst.asset == DBG_ASSET:
            try:
                DEBUG (f"trans ({trans}) / currAssetAmnt:{self.currencies[DBG_ASSET].amount}")
                dbg=1
            except:pass
        if trans.txid == DBG_TXID:
            DEBUG (f"trans ({trans})")
            dbg=1
        g = self.__swap (trans)
        for fee in trans.fees:
            self.__swapFee (src=fee, dst= None, gain=g)
        self.shortStatus()
        # Check balances
        for val in trans.bal:
            assert(val.asset in self.currencies)
            if val.value == "auto": # Do not check it for airdrops/deposits
                val.value = self.currencies[val.asset].amount
            try:
                m = max([abs(self.currencies[val.asset].amount) , abs(val.value)])
            except:
                print ([self.currencies[val.asset].amount , val.value])
                raise
            if m > 1e-4:
                delta = abs(self.currencies[val.asset].amount - val.value)/m
                if dbg:
                    DEBUG (f"Balance ({val.asset}):Found={self.currencies[val.asset]}/Exp={val.value}, m={m}, delta={delta}")
                if delta > 1e-2:
                    # print(f"While processing trans {trans}", file = sys.stderr)
                    print(f"Balance error in transaction {trans} @{trans.date}")
                    print(f"Balances: {trans.bal}")
                    print(f"- A balance of {self.currencies[val.asset].amount} {val.asset} was calculated.")
                    print(f"- A balance of {val.value} {val.asset} was found in ledger.")
                    raise BalanceError (msg=f"Found={self.currencies[val.asset].amount}/Exp={val.value}",
                                        asset=val.asset,
                                        txid=trans.txid,
                                        delta=delta)
                elif delta > 1e-6:
                    # resynchronize to avoid cumulative errors
                    # TODO : could compute and check total discrepancy.
                    self.currencies[val.asset].amount = val.value
        
        # Update mean value for asset
        
    def asString(self):
        res = {}
        for k,v in self.currencies.items():
            asset  = actualAsset(k)
            isStake = k != asset
            # isStake = len(k)>2 and (k[-2:] == ".S" or k[-2:] == ".M")
            name = asset
            if name in Ledger_Kraken.TRANSFERABLE:
                # Must concatenate 2 different Coins
                name = Ledger_Kraken.TRANSFERABLE[name]
                
            if name not in res: res[name] = (0.0,0.0,0.0, 0.0) # amount/staked/deposited/meanEurValue
            amount,staked,deposited,meanEurValue = res[name]
            if amount * meanEurValue > 1E-5:
                meanEurValue= (v.meanEurValue * v.amount + meanEurValue*amount)/(v.amount+amount)
            else:meanEurValue= v.meanEurValue
            
            if isStake:staked += v.amount
            else:amount += v.amount
            if amount < 0 and amount > -1e-8 : amount =0.0
            deposited += self.deposit[k]
            res[name] = amount,staked,deposited, meanEurValue
            
        out=[]
        # Add title
        out.append("+-------+--------------------+--------------+--------------------+")
        out.append("| Coin   | Balance            | Purch. price | Withdraw /Dep     |")
        out.append("+--------+--------------------+--------------+-------------------+")
        # Add result
        for k in sorted(res.keys()):
            amount,staked,deposited,meanEurValue = res[k]
            amount,staked = amount+staked , 0 # We don't care about stake in summary
            if abs (amount) < 1e-7 and  abs (staked) < 1e-7 and  abs (deposited) < 1e-7 :continue
            s = f"| {k:7}|{amount:>18.6f} "
            
            mbv = niceFloat(meanEurValue)
            mbv =" "*(12-len(mbv)) + mbv
            
            s += f" | {mbv} | "
            
            dw = niceFloat(abs(deposited))
            dw =" "*(12-len(dw)) + dw
            
            if deposited > 1e-7    : s += f"Dep. {dw} |"
            elif deposited < -1e-7 : s += f"With.{dw} |"
            else                   : s += " " *(18) + "|"
            
            out.append(s)
        out.append("+--------+--------------------+--------------+-------------------+")
        return out
    
class GainCalculcator(object):
    '''
    classdocs
    '''
    def __init__(self):
        '''
        Constructor
        '''
        self.wallet = Wallet()
        self.__lines=[]
        
    def inject(self, filename):
        csv = CSV_File(filename)
        sourceSite =csv.sourceSite()
        for line in csv.datas:
            trans = sourceSite.toTransaction(line)
            if trans:
                self.__lines.append(trans)
        
    def process(self, journalFile=sys.stdout):
        self.__lines.sort(key=lambda trans:trans.date)
        
        wallet = self.wallet
        for trans in self.__lines:
            #  Try to identify currency pair
            if not trans:continue
            
            
            if journalFile:
                print ("==========================", file=journalFile)
                print (f"{trans} @ {trans.date}", file=journalFile)
                
            try:
                wallet.apply(trans)
            except:
                #print(f"While processing trans {trans}",file=sys.stderr)
                #print(f"With TRANS= SRC:{trans.src}, DST:{trans.dst},  {trans.bal}",file=sys.stderr)
                raise
            if journalFile:
                print (f"New balance:{trans.bal}", file=journalFile)
                asset = trans.src.asset
                mean = wallet.currencies[asset].meanEurValue
                if asset != FIAT_EUR and mean*wallet.currencies[asset].amount > 1E-4:
                    print (f"Mean buy price for {asset} is {niceFloat(mean)} EUR", file=journalFile)
                if asset != trans.dst.asset:
                    asset = trans.dst.asset
                    mean = wallet.currencies[asset].meanEurValue
                    if asset != FIAT_EUR and mean*wallet.currencies[asset].amount > 1E-4:
                        print (f"Mean buy price for {asset} is {niceFloat(mean)} EUR", file=journalFile)
        
        print ("All operations succeeded.")

    def getTransactions(self): return self.__trans
    