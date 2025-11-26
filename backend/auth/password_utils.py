import argon2
import math
import string
from argon2.exceptions import VerifyMismatchError, InvalidHash

hasher = argon2.PasswordHasher()

def hash_password(password: str) -> str:
    """
    Hash a plain text password using Argon2 algorithm.
    
    Args:
        password (str): Plain text password to hash
        
    Returns:
        str: Argon2 hashed password string
        
    Raises:
        TypeError: If password is empty or None
        argon2.exceptions.HashingError: If hashing fails
    """
    if password:
        try:
            hashed_password = hasher.hash(password)
            return hashed_password
        except argon2.exceptions.HashingError:
            raise
    else:
        raise TypeError("Password should not be empty or None")

def validate_password_strength(password: str) -> dict:
    """
    Validate password strength based on entropy calculation.
    
    Args:
        password (str): Plain text password to validate
        
    Returns:
        dict: Contains 'valid' (bool) and either 'message' or 'strength' key
              - If weak: {"valid": False, "message": "Password is too weak"}
              - If good: {"valid": True, "strength": "Good"}  
              - If excellent: {"valid": True, "strength": "Excellent"}
    """
    entropy = calculate_entropy(password)

    if entropy < 50:
        return {"valid": False, "message": "Password is too weak"}
    elif entropy < 70: 
         return {"valid": True, "strength": "Good"}
    else:
        return {"valid": True, "strength": "Excellent"}
        
def calculate_entropy(password: str) -> float:
    """
    Calculate password entropy based on character diversity and length.
    
    Args:
        password (str): Password to analyze
        
    Returns:
        float: Entropy value in bits (higher = more secure)
        
    Note:
        Entropy = password_length * log2(character_space_size)
        Character spaces: lowercase(26) + uppercase(26) + digits(10) + symbols=len(string.punctuation)
    """
    probable_characters = 0

    if not password:
        return 0.0

    if any(c.islower() for c in password):
        probable_characters += 26

    if any(c.isupper() for c in password):
        probable_characters += 26

    if any(c.isdigit() for c in password):
        probable_characters += 10

    # Count punctuation/symbols properly (previous code used isalnum which was incorrect)
    if any(c in string.punctuation for c in password):
        probable_characters += len(string.punctuation)

    # Avoid math domain error if probable_characters is 0
    if probable_characters == 0:
        return 0.0

    entropy = len(password) * math.log2(probable_characters)

    return float(entropy)

def verify_password(password_hash: str, password: str) -> bool:
    """
    Verify a plain text password against an Argon2 hash.
    
    Returns:
        bool: True if password matches hash, False otherwise
    """
    try:
        return hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHash):
        return False
