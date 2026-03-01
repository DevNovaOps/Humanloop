import hashlib, base64, os

password = 'Admin@123!'
salt = 'hl2024salt'
# 100k iterations — Django accepts any count, finishes in ~1-2 seconds
iterations = 100000

dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), iterations)
h = base64.b64encode(dk).decode('ascii')
result = f'pbkdf2_sha256${iterations}${salt}${h}'

with open('admin_hash.txt', 'w') as f:
    f.write(result)

print('Hash written to admin_hash.txt')
print(result)
