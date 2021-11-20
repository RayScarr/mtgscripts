"""
This work is licensed under a Creative Commons Attribution-ShareAlike 4.0 International License.
https://creativecommons.org/licenses/by-sa/4.0/
Original author is dude1818 on PucaTrade.com (https://pucatrade.com/profiles/show/129317)
Modified by EddyViscosity
"""

from requests import Session
import re

# Global variables
root_url = "https://pucatrade.com"
login_url = root_url + "/login"
csv_header = "Package ID,Transaction Type,Points,Balance,Sender,Sender ID,Receiver,Receiver ID,Card name,Card ID,Foil,Date,Time\n"

## Enclose a string in quotes if it contains a comma.
# This prevents names with commas (user names or card names)
# from messing up the columns in the CSV file.
# \param[in] text Any string
# \returns The same string if it had no commas, or the
# string enclosed in double-quotes if it did
def quote_if_has_comma(text):
    if (',' in text):
        return "\"%s\"" % text
    else:
        return text

## Extract user ID and user name from an href
# \param[in] s looks like "<a href='/profiles/show/12345'>John Doe</a>"
# \returns 12345, "John Doe"
def get_name_and_id(s):
    s2 = s.split('/show/')[1]
    # Now s2 looks like "12345'>John Doe</a>"
    s3 = s2.split("'>")
    id = int(s3[0])
    name = s3[1].split("</a>")[0]

    return quote_if_has_comma(name), id

class Transaction:
    sender_name = ''
    sender_id = -1
    receiver_name = ''
    receiver_id = -1
    type = ''
    notes = ''
    package_id = ''
    card_id = ''
    card_name = ''
    foil = False
    points = 0
    running_total = 0
    date = ''
    time = ''

    # Create a Transaction object from a transaction text block
    def __init__(self,ttb):
        keysplits = ttb.split('<div class="label')
        valuesplits = ttb.split('<div class="value')
        for iks, keysplit in enumerate(keysplits):
            valuesplit = valuesplits[iks]
            ka = keysplit.find('>')+1
            kb = keysplit.find('</div>')
            key = keysplit[ka:kb].strip()
            va = valuesplit.find('>')+1
            vb = valuesplit.find('</div>')
            value = valuesplit[va:vb].strip()

            if (key == 'SENDER'):
                self.sender_name, self.sender_id = get_name_and_id(value)
            elif (key == 'TYPE'):
                if (value == 'WANT'):
                    self.type = 'TRADE FEE'
                else:
                    self.type = value
            elif (key == 'NOTES'):
                self.notes = value
            elif (key == 'POINTS'):
                self.points = int(value.replace(',',''))
            elif (key == 'RUNNING'):
                self.running_total = int(value.split('>')[-1].replace(',', ''))
            elif (key == 'RECEIVER'):
                self.receiver_name, self.receiver_id = get_name_and_id(value)
            elif (key == 'DATE'):
                s2 = value.split(' ')
                self.date = s2[0]
                self.time = s2[1]

        # Decide what to do with the information in the
        # "notes" field. This depends on the transaction type.
        if (self.type == 'TRADE'):
            # Get the card name, card ID, package ID, and foil identifier
            numbers = re.findall(r'\d+', self.notes)
            self.package_id = numbers[0]
            self.card_id = numbers[2]
            self.foil_id = (numbers[3] == 0)
            self.card_name = quote_if_has_comma(self.notes.split('</a>')[-2].split('>')[-1])

    # Return a string representation of this Transaction
    # suitable for a CSV file.
    def csv_row(self):
        return "%s,%s,%i,%i,%s,%i,%s,%i,%s,%s,%s,%s,%s\n" \
            % (self.package_id,
            self.type,
            self.points,
            self.running_total,
            self.sender_name,
            self.sender_id,
            self.receiver_name,
            self.receiver_id,
            self.card_name,
            self.card_id,
            self.foil,
            self.date,
            self.time)

    # Return a string representation of this Transaction
    # suitable for print statements
    def __repr__(self):
        if (self.type == 'TRADE'):
            return 'Package %d:\n' % self.package_id + \
                '  %s (%i) -> %s (%i)\n' % (self.sender_name, self.sender_id, self.receiver_name, self.receiver_id) + \
                '  %s for %i pp on %s at %s\n' % (self.card_name, self.points, self.date, self.time)
        elif(self.type == 'PUCASHIELD'):
            return 'PUCASHIELD for %d\n' % self.points

## Connect to Pucatrade
# \param[in] username Username as a string
# \param[in] password Password as a string
def get_session(username, password):
    """Open the session on pucatrade.com"""

    # Check first page of ledger to get dates
    url = root_url + "/account/ledger/2012-01"
    payload = {"login": username, "password": password}

    with Session() as session:
        post = session.post(login_url, data=payload)
        r = session.get(url)

    return r, payload

## Get the URL for each ledger page
# \param[in] r Session response
def get_ledger_urls(r):
    """Get the list of urls comprising the ledger"""

    print("Fetching available ledger dates...")

    urls = []
    for line in r.text.split('href="'):
        url = line.split('">')[0].split('" SELECTED>')[0]
        if "ledger/2" in url:
            urls.append(root_url + url)

    return urls

## Get all transactions from all ledger URLs
# \param[in] urls List of URLs from get_ledger_urls
# \param[in] payload Session payload
# \param[in] csvfilename Name of the CSV file to write transaction data to
def get_transactions(urls, payload, csvfilename):
    """Go through each page of ledger and sum up entries"""

    transaction_start_string = '<div class="column sender">'

    with open(csvfilename, "w") as f:
        f.write(csv_header)
        with Session() as session:
            post = session.post(login_url, data=payload)
            for url in urls:
                r = session.get(url)
                transaction_text_blocks = r.text.split(transaction_start_string)[2:]
                print(
                    f"    Adding %i transactions from %s"
                    % (len(transaction_text_blocks), url.split("/")[-1])
                )

                for ttb in transaction_text_blocks:
                    # Remove non-ASCII characters to prevent usernames
                    # with unusual characters from causing a crash later
                    f.write(Transaction(ttb.encode('ascii', 'ignore').decode('ascii')).csv_row())

if __name__ == "__main__":

    # Necessary login information
    username = input("Email address: ")
    password = input("Password: ")

    response, payload = get_session(username, password)
    while "logged-out" in response.text:
        print("Invalid credentials")
        # Ask the user for email and password until
        # login succeeds.
        username = input("Email address: ")
        password = input("Password: ")
        response, payload = get_session(username, password)

    urls = get_ledger_urls(response)

    csvfilename = "puca-transactions.csv"
    transactions = get_transactions(urls, payload, csvfilename)
    print("Transaction summary written to %s\n" % csvfilename)
