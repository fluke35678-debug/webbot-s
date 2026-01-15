import os

file_path = "main_dashboard.py"

try:
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
except UnicodeDecodeError:
    with open(file_path, "r", encoding="latin-1") as f:
        lines = f.readlines()

# Find the start of the main block
main_idx = -1
for i, line in enumerate(lines):
    if 'if __name__ == "__main__":' in line:
        main_idx = i
        break

if main_idx == -1:
    print("Main block not found")
    exit(1)

# Extract parts
before_main = lines[:main_idx]
main_block = lines[main_idx:]
shop_api_idx = -1

# Find where Shop API starts inside main_block (it was after it)
for i, line in enumerate(main_block):
    if '# --- Shop Admin API ---' in line:
        shop_api_idx = i
        break

if shop_api_idx != -1:
    # We found the shop API *after* main block start
    # Split main_block into [Actual Main] and [Shop API]
    actual_main = main_block[:shop_api_idx]
    shop_api = main_block[shop_api_idx:]
    
    # Reconstruct: Before -> Shop API -> Actual Main
    new_lines = before_main + shop_api + actual_main
    
    # Write back
    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print("Successfully reordered main_dashboard.py")
else:
    # Shop API might not be after main? Or header missing?
    # Let's search for the first endpoint
    endpoint_idx = -1
    for i, line in enumerate(main_block):
        if '/api/admin/shop/embed' in line:
            # Found endpoint. Go back a few lines to find where it starts visually or just take it.
            # Assuming it starts a few lines up or we scan up.
            # Actually, let's just use the known header '# --- Shop Admin API ---'
            # If header missing, check simple logic
            pass
    print("Shop API header not found in tail. Checking if already correct.")
    # If not found, maybe I miscalculated.
