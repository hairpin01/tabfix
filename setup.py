#!/usr/bin/env python3
from setuptools import setup, find_packages

setup(
    name="tabfix-tool",
    version="1.2.6.1",
    author="hairpin01",
    author_email="alichka240784@gmail.com",
    description="Advanced tool for fixing tab/space indentation issues",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/hairpin01/tabfix",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Quality Assurance",
        "Topic :: Utilities",
    ],
    python_requires=">=3.8",
    install_requires=[
        "tqdm>=4.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
            "twine>=4.0.0",
            "build>=0.10.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "tabfix=tabfix.__main__:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
