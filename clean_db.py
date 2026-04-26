import sys
sys.path.insert(0, '.')
from modules.storage import SecurePrintDB

db = SecurePrintDB()

# Remove manually enrolled test users that pollute the DB
test_users = ['Rayen', 'ahmed', 'rayen', 'Ali', 'mouadh', 'ademo', 'mikkel']
for name in test_users:
    db.delete_user(name)

print("\nRemaining users:")
for u in db.list_users():
    print(f"  {u[0]}")

db.close()
