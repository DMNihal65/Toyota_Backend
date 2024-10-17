# -*- coding: UTF-8 -*-
"""
Initialization For Utils Package
===========================================

This Initialization module imports the necessary functions from the modules within this package
"""
# External Imports
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext

# To get a string like this run:
# openssl rand -hex 32

# This is the secret key used for signing a token sent to the user for authentication
# SECRET_KEY = "09d25e094faa6ca2556c818166b7a9574a83f7099f6f0f4caa6cf63b88e8d3e7"

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1500
#ACCESS_TOKEN_EXPIRE_MINUTES = 1

PASSWORD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")

OAUTH2_SCHEME = OAuth2PasswordBearer(tokenUrl="/api/v1/auth")
