from setuptools import setup, find_packages

setup(
    name="digital_twin",
    version="0.1.0",
    packages=find_packages(),
    install_requires=["flexus-client-kit"],
    package_data={"": ["*.webp", "*.png", "*.html", "*.lark", "*.json"]},
)
