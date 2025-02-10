from setuptools import setup, find_packages

setup(
    name="tts-controller",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi",
        "uvicorn",
        "pydantic",
        "httpx",
        "pyyaml",
        "docker",
    ],
)
