from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    EMPLOYEE = "employee"
