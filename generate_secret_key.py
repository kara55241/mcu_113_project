from django.core.management.utils import get_random_secret_key

print("Generated SECRET_KEY:")
print(get_random_secret_key())