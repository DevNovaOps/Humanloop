import hashlib, base64

password = 'Admin@123'
salt = 'railway2024salt'
# Use 260000 iterations — still Django-compatible, faster to compute
iterations = 260000

dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), iterations)
h = base64.b64encode(dk).decode('ascii')
result = f'pbkdf2_sha256${iterations}${salt}${h}'

# Write to file to avoid any terminal buffering issues
with open('admin_hash.txt', 'w') as f:
    f.write(result + '\n')

print('DONE - check admin_hash.txt')
