import glob
import os
import re
import pandas as pd
import pdfplumber
from sqlalchemy import create_engine, text

# Initialize Database Connection
engine = create_engine('sqlite:///tdic_data.db')

# Locate all target PDF files in working directory
BUYER_MST = '0304769887'  # tax code of the buyer (our own company); never a vendor

pdf_files = (
    glob.glob('inbox/*.pdf')
    or glob.glob("TDIC's Invoices/*.pdf")
    or glob.glob('*.pdf')
)
if not pdf_files:
  raise SystemExit('No PDF files found (looked in inbox/ and the current folder)')


def find_col(header_row, include, prefer=(), exclude=()):
  """Index of the header cell matching `include`, or -1.

  Cells that also match `prefer` win; otherwise the first cell that matches
  none of `exclude`. (The old loop let the LAST matching column win, so
  'Thành tiền có thuế' beat 'Thành tiền chưa có thuế', and the bare keyword
  'amount' matched the 'VAT Amount' column.)
  """
  matches = [
      i for i, t in enumerate(header_row) if any(k in t for k in include)
  ]
  for i in matches:
    if any(k in header_row[i] for k in prefer):
      return i
  for i in matches:
    if not any(k in header_row[i] for k in exclude):
      return i
  return -1


def squeeze_digits(text):
  """'0 1 0 0 7 3 6 3 4 7' -> '0100736347' (some PDFs space out the tax code)."""
  return re.sub(r'(?:\d ){9}\d', lambda m: m.group(0).replace(' ', ''), text)

all_invoices = []
all_details = []

for pdf_path in pdf_files:
  file_name = os.path.basename(pdf_path)
  print(f"Processing file: {pdf_path}...")

  items_list = []
  invoice_no = None
  vendor_name = None
  vendor_mst = None
  buyer_name = None
  pre_tax_total = 0
  tax_rate = None
  tax_amount = 0
  grand_total = 0

  # 1. Invoice Number Extraction
  file_num = re.search(r'(\d+)', file_name)
  if file_num:
    invoice_no = file_num.group(1).zfill(8)

  try:
    with pdfplumber.open(pdf_path) as pdf:
      full_pdf_text = ''
      for p in pdf.pages:
        full_pdf_text += (p.extract_text() or '') + '\n'

      p1_lines = [l.strip() for l in full_pdf_text.split('\n') if l.strip()]

      if not invoice_no:
        inv_match = re.search(
            r'(?:số\s*hóa\s*đơn|số\s*hđ|invoice\s*no)\s*[:\.]?\s*(\d+)',
            full_pdf_text,
            re.IGNORECASE,
        )
        if inv_match:
          invoice_no = inv_match.group(1).zfill(8)
        else:
          invoice_no = file_name.split('.')[0]

      # 2. Tax Rate Extraction
      vat_pct_match = re.search(
          r'(?:thuế\s*suất|gtgt|vat)[^\n%]*?(\d+(?:[\.,]\d+)?)\s*%',
          full_pdf_text,
          re.IGNORECASE,
      )
      if vat_pct_match:
        val_str = vat_pct_match.group(1).replace(',', '.')
        tax_rate = round(float(val_str) / 100.0, 4)
      else:
        simple_pct = re.search(r'\b(0|5|8|10|15)\s*%', full_pdf_text)
        if simple_pct:
          tax_rate = round(float(simple_pct.group(1)) / 100.0, 4)

      # 3. Vendor and Buyer Parsing
      for idx, line in enumerate(p1_lines):
        line_upper = line.upper()
        line_lower = line.lower()

        # Vendor Tax Code
        if not vendor_mst and idx < 30:
          if any(
              kw in line_lower for kw in ['mã số thuế', 'tax code', 'mst']
          ):
            if not any(
                b_kw in line_lower
                for b_kw in ['người mua', 'đơn vị mua', 'khách hàng']
            ):
              mst_m = re.search(r'\b\d{10}(?:-\d{3})?\b', squeeze_digits(line))
              if mst_m and mst_m.group(0) != BUYER_MST:
                vendor_mst = mst_m.group(0)
              elif not mst_m and idx + 1 < len(p1_lines):
                next_m = re.search(
                    r'\b\d{10}(?:-\d{3})?\b', squeeze_digits(p1_lines[idx + 1])
                )
                if next_m and next_m.group(0) != BUYER_MST:
                  vendor_mst = next_m.group(0)

        # Vendor Name
        if any(
            kw in line_lower
            for kw in [
                'đơn vị bán hàng:',
                'tên đơn vị bán:',
                'tên người bán:',
                'đơn vị bán:',
            ]
        ):
          vendor_name = line.split(':')[-1].strip()
        elif 'CÔNG TY' in line_upper and not vendor_name:
          if 'TẤN DŨNG' not in line_upper and 'TAN DUNG' not in line_upper:
            vendor_name = line.strip()

        if vendor_name and 'CÔNG TY' in vendor_name.upper():
          idx_cty = vendor_name.upper().find('CÔNG TY')
          vendor_name = vendor_name[idx_cty:].strip()

        # Buyer Name
        if any(
            kw in line_lower
            for kw in [
                'tên đơn vị:',
                'họ tên người mua hàng:',
                'đơn vị mua:',
                'tên người mua:',
            ]
        ):
          buyer_name = line.split(':')[-1].strip()
        elif 'TẤN DŨNG' in line_upper and not buyer_name:
          buyer_name = line.strip()

        # Summary Totals Parsing
        if any(
            kw in line_lower
            for kw in [
                'cộng tiền hàng',
                'tiền chưa có thuế',
                'chưa có thuế gtgt',
                'tiền chưa thuế',
            ]
        ):
          m_num = re.findall(r'[\d\.,]+', line)
          if m_num:
            try:
              pre_tax_total = int(
                  round(float(m_num[-1].replace('.', '').replace(',', '.')))
              )
            except:
              pass
        elif any(
            kw in line_lower
            for kw in ['tiền thuế gtgt', 'số tiền thuế', 'tiền thuế']
        ):
          if 'thanh toán' not in line_lower:
            m_num = re.findall(r'[\d\.,]+', line)
            if m_num:
              try:
                tax_amount = int(
                    round(float(m_num[-1].replace('.', '').replace(',', '.')))
                )
              except:
                pass
        elif any(
            kw in line_lower
            for kw in [
                'tổng tiền thanh toán',
                'tổng cộng tiền thanh toán',
                'cộng tiền thanh toán',
            ]
        ):
          m_num = re.findall(r'[\d\.,]+', line)
          if m_num:
            try:
              grand_total = int(
                  round(float(m_num[-1].replace('.', '').replace(',', '.')))
              )
            except:
              pass

        # Summary row with three amounts: pre-tax, VAT, total payable
        if line_lower.startswith('tổng cộng') and 'thanh toán' not in line_lower:
          amounts = [
              int(n.replace('.', ''))
              for n in re.findall(r'\d{1,3}(?:\.\d{3})+', line)
          ]
          if len(amounts) == 3:
            pre_tax_total, tax_amount, grand_total = amounts

      if tax_rate is None or tax_rate == 0.0:
        if pre_tax_total > 0 and tax_amount > 0:
          tax_rate = round(tax_amount / pre_tax_total, 2)
        else:
          tax_rate = 0.10

      # 4. Item Detail Extraction (Dynamic Header Matching)
      for page in pdf.pages:
        tables = page.extract_tables()
        if tables:
          for table in tables:
            if not table or len(table) < 2:
              continue

            header_row = [
                str(cell).replace('\n', ' ').strip().lower() if cell else ''
                for cell in table[0]
            ]

            qty_idx = find_col(header_row, ['số lượng', 'quantity', 'qty'])
            price_idx = find_col(header_row, ['đơn giá', 'unit price'])
            total_idx = find_col(
                header_row,
                ['thành tiền', 'tổng tiền', 'amount'],
                prefer=['chưa có thuế', 'chưa thuế', 'trước thuế'],
                exclude=['có thuế', 'sau thuế', 'tiền thuế', 'vat amount'],
            )
            rate_idx = find_col(header_row, ['thuế suất'])
            unit_idx = find_col(header_row, ['đơn vị', 'đvt'])

            for row in table[1:]:
              if not row:
                continue

              clean_row = [
                  str(cell).replace('\n', ' ').strip() if cell else ''
                  for cell in row
              ]
              if not any(clean_row):
                continue

              stt_val = None
              stt_idx = -1
              for c_i, cell_val in enumerate(clean_row):
                clean_stt = cell_val.rstrip('.')
                if clean_stt.isdigit() and 1 <= int(clean_stt) <= 500:
                  stt_val = int(clean_stt)
                  stt_idx = c_i
                  break

              if stt_val is None or stt_idx + 1 >= len(clean_row):
                continue

              try:
                item_name = clean_row[stt_idx + 1].strip()
                if item_name.isdigit() or len(item_name) <= 1:
                  continue

                def parse_num(val):
                  if not val:
                    return 0.0
                  v = (
                      re.sub(r'[^\d\.,]', '', val)
                      .replace('.', '')
                      .replace(',', '.')
                  )
                  try:
                    return float(v)
                  except:
                    return 0.0

                qty = 0.0
                unit_price = 0
                line_total = 0

                if qty_idx != -1 and price_idx != -1:
                  qty = parse_num(clean_row[qty_idx])
                  unit_price = int(round(parse_num(clean_row[price_idx])))
                  line_total = (
                      int(round(parse_num(clean_row[total_idx])))
                      if total_idx != -1
                      else int(round(qty * unit_price))
                  )
                else:
                  nums = []
                  for c in clean_row[stt_idx + 2 :]:
                    f_val = parse_num(c)
                    if f_val > 0:
                      nums.append(f_val)

                  if len(nums) >= 3:
                    qty, unit_price, line_total = (
                        nums[-3],
                        int(round(nums[-2])),
                        int(round(nums[-1])),
                    )
                  elif len(nums) == 2:
                    qty, line_total = nums[0], int(round(nums[1]))
                    unit_price = (
                        int(round(line_total / qty)) if qty > 0 else 0
                    )

                if qty == 0:
                  continue

                row_rate = tax_rate
                if rate_idx != -1 and rate_idx < len(clean_row):
                  m_rate = re.search(
                      r'(\d+(?:[.,]\d+)?)\s*%', clean_row[rate_idx]
                  )
                  if m_rate:
                    row_rate = round(
                        float(m_rate.group(1).replace(',', '.')) / 100.0, 4
                    )
                unit_val = 'Cái'
                if (
                    unit_idx != -1
                    and unit_idx < len(clean_row)
                    and clean_row[unit_idx]
                ):
                  unit_val = clean_row[unit_idx]

                line_tax_amount = int(round(line_total * row_rate))
                line_grand_total = int(round(line_total + line_tax_amount))

                items_list.append({
                    'Invoice_No': invoice_no,
                    'Item_STT': stt_val,
                    'Item_Name': item_name,
                    'Unit': unit_val,
                    'Quantity': qty,
                    'Unit_Price': unit_price,
                    'Line_Total': line_total,
                    'Tax_Rate': row_rate,
                    'Tax_Amount': line_tax_amount,
                    'Grand_Total': line_grand_total,
                })
              except Exception:
                continue

        # Text Line Parsing Fallback
        page_lines = [
            l.strip()
            for l in (page.extract_text() or '').split('\n')
            if l.strip()
        ]
        for line in page_lines:
          parts = line.split()
          if not parts:
            continue

          stt_candidate = parts[0].rstrip('.')
          if stt_candidate.isdigit() and 1 <= int(stt_candidate) <= 500:
            stt_num = int(stt_candidate)
            if any(
                it['Item_STT'] == stt_num
                for it in items_list
                if it['Invoice_No'] == invoice_no
            ):
              continue

            try:
              item_name = (
                  ' '.join(parts[1:-4]) if len(parts) >= 6 else parts[1]
              )
              if item_name.strip().isdigit() or len(item_name.strip()) <= 1:
                continue

              clean_nums = []
              for p in parts[1:]:
                v_str = p.replace('.', '').replace(',', '.')
                try:
                  clean_nums.append(float(v_str))
                except ValueError:
                  pass

              if len(clean_nums) >= 3:
                qty = clean_nums[-3]
                unit_price = int(round(clean_nums[-2]))
                line_total = int(round(clean_nums[-1]))

                line_tax = int(round(line_total * tax_rate))
                line_grand = line_total + line_tax

                items_list.append({
                    'Invoice_No': invoice_no,
                    'Item_STT': stt_num,
                    'Item_Name': item_name.strip(),
                    'Unit': parts[-4] if len(parts) >= 6 else 'Cái',
                    'Quantity': qty,
                    'Unit_Price': unit_price,
                    'Line_Total': line_total,
                    'Tax_Rate': tax_rate,
                    'Tax_Amount': line_tax,
                    'Grand_Total': line_grand,
                })
            except Exception:
              continue

    if not buyer_name:
      buyer_name = (
          'CÔNG TY CỔ PHẦN ĐẦU TƯ XÂY DỰNG SẢN XUẤT THƯƠNG MẠI TẤN DŨNG'
      )

    totals_from_pdf = pre_tax_total > 0 and grand_total > 0
    if pre_tax_total == 0 and items_list:
      pre_tax_total = int(
          round(sum(item['Line_Total'] for item in items_list))
      )

    if tax_amount == 0 and pre_tax_total > 0:
      tax_amount = int(round(pre_tax_total * tax_rate))

    if grand_total == 0 and pre_tax_total > 0:
      grand_total = int(round(pre_tax_total + tax_amount))

    if not totals_from_pdf:
      print(f'  [warn] {invoice_no}: totals not found in PDF, derived from lines')
    if (
        pre_tax_total > 0
        and tax_amount > 0
        and abs(pre_tax_total * tax_rate - tax_amount) > 1
    ):
      tax_rate = round(tax_amount / pre_tax_total, 4)  # mixed-rate invoice

    all_invoices.append({
        'Invoice_No': invoice_no,
        'Vendor_Name': vendor_name if vendor_name else 'Pending',
        'Vendor_MST': vendor_mst if vendor_mst else 'N/A',
        'Buyer_Name': buyer_name,
        'Pre_Tax_Total': int(pre_tax_total),
        'Tax_Rate': tax_rate,
        'Tax_Amount': int(tax_amount),
        'Grand_Total': int(grand_total),
        'File_Name': pdf_path,
    })

    all_details.extend(items_list)

  except Exception as e:
    print(f'Error processing file {pdf_path}: {e}')

# 5. Database Writing
if all_invoices:
  df_invoices = pd.DataFrame(all_invoices)
  df_invoices = df_invoices.drop_duplicates(subset=['Invoice_No'])

  desired_order = [
      'Invoice_No',
      'Vendor_Name',
      'Vendor_MST',
      'Buyer_Name',
      'Pre_Tax_Total',
      'Tax_Rate',
      'Tax_Amount',
      'Grand_Total',
      'File_Name',
  ]
  df_invoices = df_invoices[desired_order]

  df_details = pd.DataFrame(all_details)
  if not df_details.empty:
    df_details = df_details.drop_duplicates(subset=['Invoice_No', 'Item_STT'])
    df_details = df_details.sort_values(by=['Invoice_No', 'Item_STT'])
    df_details['Unit'] = df_details['Unit'].str.strip().str.lower()

  with engine.connect() as conn:
    conn.execute(text('DROP TABLE IF EXISTS invoices;'))
    conn.execute(text('DROP TABLE IF EXISTS invoice_details;'))
    conn.commit()

  df_invoices.to_sql('invoices', con=engine, if_exists='replace', index=False)
  if not df_details.empty:
    df_details.to_sql(
        'invoice_details', con=engine, if_exists='replace', index=False
    )

  print('\n=== PARSING COMPLETED ===')
  print(f'Total Invoices Processed: {len(df_invoices)}')
  print(f'Total Detailed Line Items Extracted: {len(df_details)}')