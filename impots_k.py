'''
Created on 16 avr. 2023

@author: MAO
'''
import sys
import os
import datetime

sys.path.append("impots")
from read_csv import CalcExcept, BalanceError
from calculator import GainCalculcator
from journal import JTransaction 


def printE(s):print (s, file = sys.stderr)

def showHelp():
    print ("Extract a Kraken ledger extract and provides gains on a given year.")
    print ("The Kraken exports must be placed in 'files/ledgers{YEAR}.csv'")
    print ("External operations must be placed (and filled manually) in 'files/deposits{YEAR}.csv'")
    print ("Usage:")
    print (" -i       : interactive mode.")
    print (f" -y<YYYY> : Specify Year(default={YEAR}.")
    print (" --help   : This help.")
if __name__ == '__main__':
    INTERACTIVE=False
    YEAR=datetime.date.today().year - 1
    
    for p in sys.argv[1:] :
        if p == '--help': showHelp(); sys.exit(0)
        if p == '-i':  INTERACTIVE =True; continue
        if p == '-y':
            YEAR=int(p[2:])
            continue
        print(f"Unknown option '{p}'. Use --help for help.")
        sys.exit(1)
    print(f"Using YEAR={YEAR}")
    try:
        DO_DEBUG=0
        
        decl = {}
        gains = GainCalculcator()
        gains.inject(f'files/deposits{YEAR}.csv')
        gains.inject(f'files/ledgers{YEAR}.csv')
        
        outDir = "out"
        outname = f"justifImpots{YEAR}.csv"
        journalName = f"journalComplet{YEAR}.csv"
        
        # Create output dir
        if not os.path.exists(outDir):
            try:
                os.mkdir(outDir)
            except Exception as E:
                print(f"Failed to create folder {outDir}")
                sys.exit(1)
                
        try:
            journal = open(os.path.join(outDir, journalName), "w")
        except Exception as E:
            print(f"Saving to CSV file {outname} failed")
            sys.exit(1)

        gains.process(journalFile=journal)
        
        try:
            totalCost = 0
            valuation = 0
            fees =0
            decl[211] = None
            with open(os.path.join(outDir, outname), "w") as outFile:
                print (f'"date","txid","gain","total"', file =outFile)
                _sum = 0.0
                for cgain in gains.wallet.gains:
                    t = cgain.trans
                    tVal = abs(cgain.tVal)
                    g = cgain.gain
                    if abs(g) + abs(cgain.deposit) < 1e-7:continue
                    if t.date.year != YEAR : continue
                    totalCost += tVal
                    valuation = abs(cgain.wVal)
                    _sum += g
                    fees -= cgain.fees
                    decl[211]=t.date.strftime("%d/%m/%Y")
                    print (f"{t.date},{t.txid},{g:+7.2f},{_sum:+7.2f}", file =outFile)
        
            decl[212] = int(totalCost+_sum)
            decl[213] = int(totalCost+_sum)
            decl[214] = int(fees) #Frais
            decl[215] = int(decl[213] - decl[214]) #Frais
            
            decl[216]= 0
            decl[217] = decl[213] - decl[216]
            decl[218]= decl[213] - decl[214]
            decl[220] = int(totalCost)
            decl[221]= 0
            decl[222]= 0
            decl[223]= decl[220] - decl[221] - decl[222]
            decl[224]= int(decl[218] - (decl[223] * decl[217] / decl[212]) )
            
            print (f"For Year {YEAR}: cost ={totalCost:+7.2f}, sold={totalCost+_sum:+7.2f}, gain ={_sum:+7.2f}, valuation={valuation:+7.2f}")
            for n in sorted(list(decl.keys())):
                print(f" 2086.{n} : {decl[n]}")
        except Exception as E:
            printE(f"Saving to CSV file {outname} failed")
            raise
            sys.exit(1)
                
        journal.close()    
            
        print (f"Wallet content: ({gains.wallet.lastTransactionDate})")
        print ("\n".join(gains.wallet.asString()))
        
        for y in sorted(gains.wallet.gainsByYear):
            print(f"Year {y} : Gains = {gains.wallet.gainsByYear[y]:+5.0f} EUR")
    except CalcExcept as E: 
        printE (f"Error : {E}")
        if DO_DEBUG:raise E
        sys.exit(1)
    except BalanceError as E:
        printE (f"While processing transaction {E.txid}:")
        printE (f" -> Invalid balance in ledgers for {E.asset}: {E.msg}")
        try: fstDate = gains.wallet.firstTransactionDate
        except:fstDate=None
        printE (f"    This problem is generally due to :")
        printE (f"     - an incomplete ledgers<YYYY>.csv exports from KRAKEN")
        printE (f"       (You MUST export LEDGERS starting from the account opening, not only the current year.)")
        printE (f"     - an incomplete deposits<YYYY>.csv exports from KRAKEN")
        printE (f"       (You MUST manually add all deposits in this file.)")
        printE (f"    => You possibly forgot to add an entry in this file for a deposit of {E.delta} {E.asset}")
        if fstDate != None:
            printE (f"  Note : Your LEDGERS entries start at {fstDate}")
        if not INTERACTIVE : sys.exit(1)
    except Exception as E:
        printE (f"Error : {E}")
        if not INTERACTIVE :  raise E
        
    # Interactive mode
    if INTERACTIVE:
        _help=True
        while True:
            if _help:
                print("Entering interactive mode (case INsensitive). Commands:")
                print("  - 'Q' to quit")
                print("  - '?' to show all assets")
                print("  - '/D' to show all deposits")
                print("  - '/M' to switch MeanValue display")
                print("  - '/A' to switch Amount display")
                print("  - <ASSET_NAME> to show all entries of a given asset")
                _help=False
            l =  input(">").upper()
            if not l: _help=True; continue
            if l == "Q" : break
            if l == "?" : # List all assets
                print ("\n".join(str(t) for t in sorted(list(gains.wallet.journal.allAssets))))
                continue
            if l == "/M" : JTransaction.ShowMeanV = not JTransaction.ShowMeanV ;continue
            if l == "/A" : JTransaction.ShowAmount = not JTransaction.ShowAmount ;continue
            if l == "/D" :
                transList= gains.wallet.journal.getByType("D")
                print ("\n".join(str(t) for t in transList))
                continue
            transList= gains.wallet.journal.getByAsset(l)
            if not transList:
                print(f"Unknown asset {l}")
                _help=True
            print ("\n".join(str(t) for t in transList))
            
        
    print("Terminated successfully")