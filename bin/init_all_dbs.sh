


python scripts/drop_daylily_tables.py --region us-west-2 --force

python scripts/drop_daylily_tables.py --region us-west-2 --force
# then type DELETE when prompted


./bin/daylily-workset-api \
  --table-name daylily-worksets \
  --region us-west-2 \
  --create-table \
  --port 8000

python scripts/init_file_registry_tables.py --region us-west-2


python3 << 'EOF'
from daylib.workset_customer import CustomerManager
cm = CustomerManager(region="us-west-2")
cm.create_customer_table_if_not_exists()
print("✓ customer table created (", cm.customer_table_name, ")")
EOF