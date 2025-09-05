import pandas as pd
import re
import os
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

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
        # Format 1 has Debit/Credit, Format 2 has a single Amount column
        header_format1 = ['Transaction Date', 'Posted Date', 'Card No.', 'Description', 'Category', 'Debit', 'Credit', 'Notes']
        
        # The second format's header is often not present, so we infer columns
        
        is_format2 = False
        
        for i, line in enumerate(lines):
            # Skip empty or header lines
            if not line.strip() or 'Transaction Date' in line:
                continue

            # A common issue is extra commas, so we split and handle potential errors
            parts = line.strip().split(',')
            
            # Detect switch to the second, simpler format
            # This format often starts with a date and has fewer, misaligned columns
            try:
                # Attempt to parse what would be the 'Amount' column in format 2
                float(parts[3])
                if len(parts) <= 6:
                     is_format2 = True
            except (ValueError, IndexError):
                pass # Continue assuming format 1 if parsing fails

            try:
                if not is_format2:
                    # --- PARSE FORMAT 1 (Debit/Credit columns) ---
                    debit = pd.to_numeric(parts[5], errors='coerce')
                    credit = pd.to_numeric(parts[6], errors='coerce')
                    
                    amount = debit if pd.notna(debit) else -credit if pd.notna(credit) else 0
                    
                    transactions.append({
                        'Transaction Date': pd.to_datetime(parts[0]),
                        'Description': parts[3],
                        'Category': parts[4],
                        'Amount': amount,
                        'Notes': parts[7] if len(parts) > 7 else ''
                    })
                else:
                    # --- PARSE FORMAT 2 (Single Amount column) ---
                    # This format appears to be misaligned in the source CSV
                    transactions.append({
                        'Transaction Date': pd.to_datetime(parts[0]),
                        'Description': parts[2],
                        'Category': parts[4],
                        'Amount': float(parts[3]),
                        'Notes': ''
                    })
            except Exception:
                # This helps skip any malformed lines that can't be parsed
                print(f"Warning: Could not parse line {i+1}: {line.strip()}")
                continue

        if not transactions:
            print("Error: No valid transactions could be parsed.")
            return None
            
        df = pd.DataFrame(transactions)
        df = df.dropna(subset=['Transaction Date', 'Amount'])
        df = df[df['Amount'] != 0] # Exclude zero-amount transactions
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
    
    # Define rules from most specific to most general
    vendor_rules = {
        'AMAZON|AMZN': 'Amazon',
        'TESCO': 'Tesco',
        'EBAY': 'eBay',
        'GOOGLE.*YOUTUBE': 'Google YouTube Premium',
        'UBER': 'Uber',
        'STARBUCKS': 'Starbucks',
        'PANDA EXPRESS': 'Panda Express',
        'SAFEWAY': 'Safeway',
        'CIRCUIT GO': 'Circuit Laundry',
        'SUMUP \*\* (.*)': r'\1',  # Extract vendor from SumUp
        'SQ \*(.*)': r'\1',  # Extract vendor from Square
        'TIM HORTONS': 'Tim Hortons',
        'UNIVERSITY COLLEGE|STEPHENSON COLLEGE|DURHAM STUDENTS': 'Durham University',
        'CAPITAL ONE.*PYMT': 'Capital One Payment',
        'INTERNET PAYMENT|DIRECTPAY': 'Bank Payment',
        'CASH BACK|CASHBACK|REWARD': 'Cash Back / Rewards',
    }

    for pattern, name in vendor_rules.items():
        match = re.search(pattern, description)
        if match:
            # If the name is a regex capture group, use it
            if '\\' in name:
                return match.group(1).strip().title()
            return name

    # Default fallback if no rules match
    return description.title()

def generate_summary_report(df, output_path='financial_summary.txt'):
    """
    Generates a text-based summary report of the financial data.

    Args:
        df (pandas.DataFrame): The DataFrame containing transaction data.
        output_path (str): The file path for the output summary report.
    """
    spending_df = df[df['Amount'] > 0]
    payments_df = df[df['Amount'] < 0]

    with open(output_path, 'w') as f:
        f.write("=======================================\n")
        f.write("      PERSONAL FINANCE SUMMARY\n")
        f.write("=======================================\n\n")

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
    """
    Groups transactions by vendor and category and exports the result to a new CSV file.

    Args:
        df (pandas.DataFrame): The DataFrame containing transaction data.
        output_path (str): The file path for the output CSV.
    """
    # Group by vendor and aggregate
    grouped = df.groupby(['Vendor', 'Category']).agg(
        Total_Amount=('Amount', 'sum'),
        Transaction_Count=('Amount', 'count'),
        First_Transaction_Date=('Transaction Date', 'min'),
        Last_Transaction_Date=('Transaction Date', 'max')
    ).sort_values(by='Total_Amount', ascending=True).reset_index()

    grouped.to_csv(output_path, index=False)
    print(f"\n[Success] Grouped transactions exported to '{output_path}'")

def plot_spending_by_category(df, output_path='spending_by_category.png'):
    """
    Creates and saves a bar chart of spending by category.

    Args:
        df (pandas.DataFrame): The DataFrame containing transaction data.
        output_path (str): The file path for the output image.
    """
    spending_df = df[df['Amount'] > 0]
    category_spending = spending_df.groupby('Category')['Amount'].sum().sort_values(ascending=False)

    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(12, 8))
    
    sns.barplot(x=category_spending.values, y=category_spending.index, palette='viridis', ax=ax)
    ax.set_title('Total Spending by Category', fontsize=16, weight='bold')
    ax.set_xlabel('Total Amount ($)', fontsize=12)
    ax.set_ylabel('Category', fontsize=12)
    
    # Add value labels to bars
    for i, v in enumerate(category_spending.values):
        ax.text(v + 1, i + .1, f"${v:,.0f}", color='black', fontweight='medium')

    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    print(f"\n[Success] Spending by category chart saved to '{output_path}'")

def interactive_search(df):
    """
    Allows the user to interactively search for transactions by keyword.
    """
    while True:
        keyword = input("\nEnter a keyword to search for (or 'exit' to return to menu): ").strip()
        if keyword.lower() == 'exit':
            break
        if not keyword:
            continue
            
        results = df[df['Description'].str.contains(keyword, case=False, na=False)]
        
        if results.empty:
            print(f"No transactions found matching '{keyword}'.")
        else:
            print(f"\n--- Found {len(results)} transaction(s) matching '{keyword}' ---")
            for _, row in results.iterrows():
                print(f"{row['Transaction Date'].strftime('%Y-%m-%d')} | ${row['Amount']:>8.2f} | {row['Vendor']} ({row['Category']})")

def main():
    """
    Main function to run the finance manager application.
    """
    input_file = 'fullCreditCardTransacationLedger.csv'
    
    print("Welcome to the Personal Finance Manager!")
    print(f"Attempting to load and process '{input_file}'...")
    
    master_df = clean_and_combine_data(input_file)
    
    if master_df is None:
        print("Could not process the transaction file. Exiting.")
        return
        
    # Apply smart vendor grouping
    master_df['Vendor'] = master_df['Description'].apply(get_smart_vendor)
    print(f"Successfully processed {len(master_df)} transactions.")

    while True:
        print("\n" + "="*15 + " MENU " + "="*15)
        print("1. Generate Financial Summary Report (.txt)")
        print("2. Export Grouped Transactions (.csv)")
        print("3. Create Spending by Category Chart (.png)")
        print("4. Interactive Transaction Search")
        print("5. Exit")
        
        choice = input("Please select an option (1-5): ").strip()
        
        if choice == '1':
            generate_summary_report(master_df)
        elif choice == '2':
            export_grouped_csv(master_df)
        elif choice == '3':
            plot_spending_by_category(master_df)
        elif choice == '4':
            interactive_search(master_df)
        elif choice == '5':
            print("Thank you for using the Personal Finance Manager. Goodbye!")
            break
        else:
            print("Invalid choice. Please enter a number between 1 and 5.")

if __name__ == '__main__':
    main()
