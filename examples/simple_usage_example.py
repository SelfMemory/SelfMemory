#!/usr/bin/env python3
"""
Simple SelfMemory Client Example

A minimal example showing how to use SelfMemoryClient with just an API key.
No need to specify host - it will be auto-discovered!
"""

from selfmemory import SelfMemoryClient


def main():
    # Just provide your API key - host will be auto-discovered!
    client = SelfMemoryClient(api_key="sk_im_f9dd000733fe7feb0218aeb0e8300c1e87842dac")

    # Add memories
    result1 = client.add(
        "I have a BMW bike.", tags="personal,vehicle", topic_category="personal"
    )
    print(f"Added memory 1: {result1}")

    result2 = client.add(
        "I live in Amazon", tags="personal,location", topic_category="personal"
    )
    print(f"Added memory 2: {result2}")

    # Search memories
    results = client.search("bike")
    print(f"Search results: {results}")

    # Get all memories
    all_memories = client.get_all()
    print(f"All memories: {all_memories}")

    # Close client
    client.close()


if __name__ == "__main__":
    main()
