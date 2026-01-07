import pandas as pd
import re
import os
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import configparser

def clean_and_combine_data(input_csv_path):
    """
    Loads a CSV file that may contain multiple concatenated transaction formats,
    cleans the data, and combines it into a single standardized DataFrame.

    Args:
        input_csv_path (str): The file path for the input CSV.

    Returns:
        pandas.DataFrame: A cleaned and combined DataFrame of all transactions,
                          or None if the file cannot be processed.
    """
    try:
        # Read the raw file line by line to handle structural inconsistencies
        with open(input_csv_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        transactions = []
        
        # Heuristic to detect the two known formats in the file
        is_format2 = False
        
        for i, line in enumerate(lines):
            # Skip empty or header lines
            if not line.strip() or 'Transaction Date' in line:
                continue

            parts = line.strip().split(',')
            
            # Detect switch to the second, simpler format
            try:
                float(parts[3])
                if len(parts) <= 6:
                     is_format2 = True
            except (ValueError, IndexError):
                pass 

            try:
                if not is_format2:
                    debit = pd.to_numeric(parts[5], errors='coerce')
                    credit = pd.to_numeric(parts[6], errors='coerce')
                    amount = debit if pd.notna(debit) else -credit if pd.notna(credit) else 0
                    transactions.append({
                        'Transaction Date': pd.to_datetime(parts[0]),
                        'Description': parts[3], 'Category': parts[4], 'Amount': amount,
                        'Notes': parts[7] if len(parts) > 7 else ''
                    })
                else:
                    transactions.append({
                        'Transaction Date': pd.to_datetime(parts[0]),
                        'Description': parts[2], 'Category': parts[4],
                        'Amount': float(parts[3]), 'Notes': ''
                    })
            except Exception:
                print(f"Warning: Could not parse line {i+1}: {line.strip()}")
                continue

        if not transactions:
            print("Error: No valid transactions could be parsed.")
            return None
            
        df = pd.DataFrame(transactions)
        df = df.dropna(subset=['Transaction Date', 'Amount'])
        df = df[df['Amount'] != 0]
        df['Category'] = df['Category'].fillna('Uncategorized')
        
        return df

    except FileNotFoundError:
        print(f"Error: The file '{input_csv_path}' was not found.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while processing the file: {e}")
        return None

def get_smart_vendor(description):
    """
    Applies a set of rules to clean up and consolidate transaction descriptions
    into standardized vendor names.

    Args:
        description (str): The raw transaction description.

    Returns:
        str: A cleaned and standardized vendor name.
    """
    description = str(description).upper()
    
    vendor_rules = {
        'AMAZON|AMZN': 'Amazon', 'TESCO': 'Tesco', 'EBAY': 'eBay',
        'GOOGLE.*YOUTUBE': 'Google YouTube Premium', 'UBER': 'Uber',
        'STARBUCKS': 'Starbucks', 'PANDA EXPRESS': 'Panda Express',
        'SAFEWAY': 'Safeway', 'CIRCUIT GO': 'Circuit Laundry',
        r'SUMUP \*\* (.*)': r'\1', r'SQ \*(.*)': r'\1',
        'TIM HORTONS': 'Tim Hortons',
        'UNIVERSITY COLLEGE|STEPHENSON COLLEGE|DURHAM STUDENTS': 'Durham University',
        'CAPITAL ONE.*PYMT': 'Capital One Payment',
        'INTERNET PAYMENT|DIRECTPAY': 'Bank Payment',
        'CASH BACK|CASHBACK|REWARD': 'Cash Back / Rewards',
    }

    for pattern, name in vendor_rules.items():
        match = re.search(pattern, description)
        if match:
            if '\\' in name:
                return match.group(1).strip().title()
            return name

    return description.title()

def generate_summary_report(df, output_path='financial_summary.txt'):
    """Generates a text-based summary report of the financial data."""
    spending_df = df[df['Amount'] > 0]
    payments_df = df[df['Amount'] < 0]

    with open(output_path, 'w') as f:
        f.write("="*39 + "\n")
        f.write("      PERSONAL FINANCE SUMMARY\n")
        f.write("="*39 + "\n\n")
        f.write(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Date Range: {df['Transaction Date'].min().strftime('%Y-%m-%d')} to {df['Transaction Date'].max().strftime('%Y-%m-%d')}\n\n")
        f.write("--- Overall Summary ---\n")
        f.write(f"Total Spending: ${spending_df['Amount'].sum():,.2f}\n")
        f.write(f"Total Payments/Credits: ${-payments_df['Amount'].sum():,.2f}\n")
        f.write(f"Net Activity: ${df['Amount'].sum():,.2f}\n\n")
        f.write("--- Spending by Category ---\n")
        category_spending = spending_df.groupby('Category')['Amount'].sum().sort_values(ascending=False)
        for category, total in category_spending.items():
            f.write(f"{category:<25} ${total:,.2f}\n")
        f.write("\n--- Top 10 Vendors by Spending ---\n")
        vendor_spending = spending_df.groupby('Vendor')['Amount'].sum().sort_values(ascending=False)
        for vendor, total in vendor_spending.head(10).items():
            f.write(f"{vendor:<25} ${total:,.2f}\n")
    print(f"\n[Success] Financial summary report saved to '{output_path}'")

def export_grouped_csv(df, output_path='grouped_transactions.csv'):
    """Groups transactions by vendor and category and exports to a CSV file."""
    grouped = df.groupby(['Vendor', 'Category']).agg(
        Total_Amount=('Amount', 'sum'),
        Transaction_Count=('Amount', 'count'),
        First_Transaction_Date=('Transaction Date', 'min'),
        Last_Transaction_Date=('Transaction Date', 'max')
    ).sort_values(by='Total_Amount', ascending=False).reset_index()
    grouped.to_csv(output_path, index=False)
    print(f"\n[Success] Grouped transactions exported to '{output_path}'")

def plot_spending_by_category(df, output_path='spending_by_category.png'):
    """Creates and saves a bar chart of spending by category."""
    spending_df = df[df['Amount'] > 0]
    category_spending = spending_df.groupby('Category')['Amount'].sum().sort_values(ascending=False)
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(12, 8))
    sns.barplot(x=category_spending.values, y=category_spending.index, palette='viridis', ax=ax)
    ax.set_title('Total Spending by Category', fontsize=16, weight='bold')
    ax.set_xlabel('Total Amount ($)', fontsize=12)
    ax.set_ylabel('Category', fontsize=12)
    for i, v in enumerate(category_spending.values):
        ax.text(v + 1, i + .1, f"${v:,.0f}", color='black', fontweight='medium')
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    print(f"\n[Success] Spending by category chart saved to '{output_path}'")

def interactive_search(df):
    """Allows the user to interactively search for transactions by keyword."""
    while True:
        keyword = input("\nEnter a keyword to search for (or 'exit' to return to menu): ").strip()
        if keyword.lower() == 'exit': break
        if not keyword: continue
        results = df[df['Description'].str.contains(keyword, case=False, na=False)]
        if results.empty:
            print(f"No transactions found matching '{keyword}'.")
        else:
            print(f"\n--- Found {len(results)} transaction(s) matching '{keyword}' ---")
            sorted_results = results.sort_values(by='Amount', ascending=False)
            for _, row in sorted_results.iterrows():
                print(f"{row['Transaction Date'].strftime('%Y-%m-%d')} | ${row['Amount']:>8.2f} | {row['Vendor']} ({row['Category']})")

def generate_full_vendor_report(df, output_path='full_vendor_report.txt'):
    """Generates a text file listing all vendors sorted by total spending."""
    spending_df = df[df['Amount'] > 0]
    vendor_spending = spending_df.groupby('Vendor')['Amount'].sum().sort_values(ascending=False)
    with open(output_path, 'w') as f:
        f.write("="*39 + "\n")
        f.write("      FULL VENDOR SPENDING REPORT\n")
        f.write("="*39 + "\n\n")
        f.write("All vendors, sorted by total amount spent.\n\n")
        for vendor, total in vendor_spending.items():
            f.write(f"{vendor:<40} ${total:,.2f}\n")
    print(f"\n[Success] Full vendor spending report saved to '{output_path}'")

def plot_monthly_spending(df, output_path='monthly_spending_chart.png'):
    """Creates and saves a line chart of spending by month."""
    spending_df = df[df['Amount'] > 0].copy()
    spending_df['Month'] = spending_df['Transaction Date'].dt.to_period('M')
    monthly_spending = spending_df.groupby('Month')['Amount'].sum()
    
    # Ensure the index is a proper timestamp for plotting
    monthly_spending.index = monthly_spending.index.to_timestamp()

    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(12, 7))
    monthly_spending.plot(kind='line', ax=ax, marker='o', linestyle='-')
    ax.set_title('Total Spending Over Time', fontsize=16, weight='bold')
    ax.set_xlabel('Month', fontsize=12)
    ax.set_ylabel('Total Spending ($)', fontsize=12)
    ax.grid(True, which='both', linestyle='--', linewidth=0.5)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    print(f"\n[Success] Monthly spending chart saved to '{output_path}'")

def check_budgets(df):
    """Checks current month's spending against budgets defined in config.ini."""
    CONFIG_FILE = 'config.ini'
    config = configparser.ConfigParser()

    # Create a default config file if it doesn't exist
    if not os.path.exists(CONFIG_FILE):
        config['Budgets'] = {
            '# Add your monthly budget for each category below (e.g., Dining = 200)': None,
            'Dining': '150',
            'Merchandise': '300',
            'Restaurants': '200',
            'Other Travel': '100',
            'Entertainment': '75'
        }
        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)
        print(f"\n[Info] A default budget file '{CONFIG_FILE}' has been created.")
        print("Please edit it with your personal monthly budgets.")
        return

    config.read(CONFIG_FILE)
    if 'Budgets' not in config:
        print(f"\n[Error] Your '{CONFIG_FILE}' is missing the [Budgets] section.")
        return
        
    budgets = {category.title(): float(amount) for category, amount in config['Budgets'].items()}
    
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    monthly_df = df[(df['Transaction Date'].dt.month == current_month) & 
                    (df['Transaction Date'].dt.year == current_year) & 
                    (df['Amount'] > 0)]
                    
    if monthly_df.empty:
        print(f"\nNo spending recorded for the current month ({datetime.now().strftime('%B %Y')}).")
        return

    category_spending = monthly_df.groupby('Category')['Amount'].sum()

    print("\n" + "="*45)
    print(f"  BUDGET vs. SPENDING ({datetime.now().strftime('%B %Y')})")
    print("="*45)
    print(f"{'Category':<20} | {'Budget':>10} | {'Spent':>10} | {'Remaining':>10}")
    print("-"*45)

    for category, budget in budgets.items():
        spent = category_spending.get(category, 0)
        remaining = budget - spent
        status = f"${remaining:,.2f}"
        if remaining < 0:
            status += " (Over)"
        
        print(f"{category:<20} | ${budget:>9,.2f} | ${spent:>9,.2f} | {status:>10}")

def main():
    """Main function to run the finance manager application."""
    input_file = 'fullCreditCardTransacationLedger.csv'
    
    print("Welcome to the Personal Finance Manager!")
    print(f"Attempting to load and process '{input_file}'...")
    master_df = clean_and_combine_data(input_file)
    
    if master_df is None:
        print("Could not process the transaction file. Exiting.")
        return
        
    master_df['Vendor'] = master_df['Description'].apply(get_smart_vendor)
    print(f"Successfully processed {len(master_df)} transactions.")

    while True:
        print("\n" + "="*15 + " MENU " + "="*15)
        print("1. Generate Financial Summary Report (.txt)")
        print("2. Export Grouped Transactions (.csv)")
        print("3. Create Spending by Category Chart (.png)")
        print("4. Interactive Transaction Search")
        print("5. Generate Full Vendor Spending Report (.txt)")
        print("6. Generate Monthly Spending Chart (.png)")
        print("7. Check Monthly Budgets")
        print("8. Exit")
        
        choice = input("Please select an option (1-8): ").strip()
        
        if choice == '1': generate_summary_report(master_df)
        elif choice == '2': export_grouped_csv(master_df)
        elif choice == '3': plot_spending_by_category(master_df)
        elif choice == '4': interactive_search(master_df)
        elif choice == '5': generate_full_vendor_report(master_df)
        elif choice == '6': plot_monthly_spending(master_df)
        elif choice == '7': check_budgets(master_df)
        elif choice == '8':
            print("Thank you for using the Personal Finance Manager. Goodbye!")
            break
        else:
            print("Invalid choice. Please enter a number between 1 and 8.")

if __name__ == '__main__':
    main()

