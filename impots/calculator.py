'''
Created on 16 avr. 2023

@author: MAO
'''
import sys

from datetime import datetime

from read_csv import CSV_File, Transaction,CalcExcept, AValue, DEBUG, BalanceError, DEPOSIT_EUR_FEE

FIAT_EUR="ZEUR"

def isEURO(asset):return asset == FIAT_EUR

class FValue(object): # A value associated with a mean FIAT value
    def __init__(self, asset):
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
        self.currencies={} # A {asset:FValue} dict
        self.depositEUR = 0.0
        self.deposit={FIAT_EUR:0.0, DEPOSIT_EUR_FEE:0.0}  # asset:value (includes staking) 
        self.gains = []
        self.gainsByYear = {}
        self.gainTotal = 0.0
        self.lastTransactionDate = None # (date)
        self.firstTransactionDate = None # (date)
        
    
    def shortStatus(self):
        return f"gains:{self.gainTotal}, injected:{self.depositEUR}"
        
    def valuationDeposit(self):
        return self.deposit[DEPOSIT_EUR_FEE] *1.0 # Just used to check and log external non-EURO deposits
    def valuationEUR(self):
        return sum(c.valuationEUR() for _,c in self.currencies.items()) - self.deposit[FIAT_EUR] * 1.0
    def __swapFee(self, src, dst):
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
        
    def __swap(self, trans :Transaction):
        # for breakpoint:
        if trans.txid == "Q4NRRFH-AAJ3V4-XCCVIW":
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
        
        if 1:
            if not (src.value <= 0):  raise Exception( f"Wallet.swap(src.value={src.value})")
            currSrc = self.currencies[src.asset]
            currDst = self.currencies[dst.asset]
            dstPrevAmount = currDst.amount
            currSrc.amount += src.value
            currDst.amount += dst.value
            transactionValuation = abs (currSrc.meanEurValue * src.value)
            if currSrc.amount < -1e-6:
                missing=currDst.amount
                currSrc.amount -= dst.value
                raise CalcExcept(f"Cannot remove {src} from wallet(current funds:{currSrc.amount}: not enough funds (Missing {missing})")
            # update valuation
            if not dst.asset in self.deposit : self.deposit[dst.asset] = 0.0
            if reason == "deposit":
                self.deposit[dst.asset] += 1.0 * dst.value
                # print(f"Deposited {dst} => {self.deposit[dst.asset]} ")
            elif reason == "withdrawal":
                # prev = self.deposit[dst.asset]
                self.deposit[dst.asset] += 1.0 * src.value
                # print(f"Withdrawn {dst} :{prev} => {self.deposit[dst.asset]} ")
                # Note : withdraw can be negative due to staking
                pass
            else:
                # The "src" wallet value is alrady up to date (only amount changed, mean value is not modified)
                # The Dst wallet mean value must be recomputed
                dstTotalValue = (currDst.meanEurValue  * dstPrevAmount) + transactionValuation
                
                if currDst.amount > 1e-8:
                    currDst.meanEurValue = dstTotalValue / currDst.amount
                # print(f"Mean value for {dst} changed to {currDst.meanEurValue}")
#         else:
#             # old method
#             self.currencies[src.asset].sell(src.value, dst)
#             
#             if dst is None: return
#             
#             if not (dst.value >= 0):  raise Exception( f"amount={dst.value}")
#             self.currencies[dst.asset].buy(dst.value, src)
        self.depositEUR = self.deposit[FIAT_EUR]
        if reason not in ["staking"]: # Avoid useless logs
            # Now, update the estimated value of wallet
            newValuation = self.valuationEUR()
            depositDelta = self.valuationDeposit() - oldDeposit
            gain =newValuation-oldValuation
            gainRes = (trans, gain, depositDelta)
            self.gains.append(gainRes)
            self.gainTotal += gain
            date = trans.date
            assert (type(date) == datetime)
            year = date.date().year
            assert(year > 1990)
            if year not in self.gainsByYear: self.gainsByYear[year] = 0.0
            self.gainsByYear[year] += gain
#             print (f"Valuation :{gainRes} / deposit:{self.depositEUR} EUR")
        return
        
        
    def apply(self, trans : Transaction):
        self.__swap (trans)
        for fee in trans.fees:
            self.__swapFee (src=fee, dst= None)
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
                DEBUG (f"Balance ({val.asset}):Found={self.currencies[val.asset]}/Exp={val.value}, m={m}, delta={delta}")
                if delta > 1e-3:
                    # print(f"While processing trans {trans}", file = sys.stderr)
                    raise BalanceError (msg=f"Found={self.currencies[val.asset].amount}/Exp={val.value}",
                                        asset=val.asset,
                                        txid=trans.txid)
                elif delta > 1e-6:
                    # resynchronize to avoid cumulative errors
                    # TODO : could compute and check total discrepancy.
                    self.currencies[val.asset].amount = val.value
        
        # Update mean value for asset
        
    def asString(self):
        res = {}
        for k,v in self.currencies.items():
            isStake = len(k)>2 and k[-2:] == ".S"
            name = k[:-2] if isStake else k[:]
            if name not in res: res[name] = (0.0,0.0,0.0) # amount/staked/deposited
            amount,staked,deposited = res[name]
            if isStake:staked += v.amount
            else:amount += v.amount
            if amount < 0 and amount > -1e-8 : amount =0.0
            deposited += self.deposit[k]
            
            res[name] = amount,staked,deposited
        out=[]
        for k in sorted(res.keys()):
            amount,staked,deposited = res[k]
            if abs (amount) < 1e-7 and  abs (staked) < 1e-7 and  abs (deposited) < 1e-7 :continue
            s = f"{k:7}:{amount:>18.6f} "
            if staked > 1e-7     : s += f" Stake:{staked:>16.6f}  "
            else                 : s += " " *(16+9)
            
            if deposited > 1e-7   : s += f"Deposited:{deposited:>16.6f}  "
            elif deposited < -1e-7 : s += f"Withdrawn:{-deposited:>16.6f}  "
            else                   : s += " " *(16+12)
            
            buyVal = self.currencies[k].meanEurValue 
            s+= f"{buyVal:>+10.2f}"
            out.append(s)
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
                if asset != FIAT_EUR:
                    print (f"Mean buy price for {asset} is {mean} EUR", file=journalFile)
                asset = trans.dst.asset
                mean = wallet.currencies[asset].meanEurValue
                if asset != FIAT_EUR:
                    print (f"Mean buy price for {asset} is {mean} EUR", file=journalFile)
        
        print ("All operations succeeded.")

    def getTransactions(self): return self.__trans
    