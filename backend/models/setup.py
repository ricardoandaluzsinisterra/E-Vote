from setuptools import setup, find_packages

setup(
    name="evote-models",
    version="0.1.0",
    description="Shared model package for E-Vote services",
    packages=find_packages(where="."),
    include_package_data=True,
)
