# Async Parallelism Guide

## 1. Introduction to Async Parallelism

Async parallelism is a programming paradigm that allows multiple operations to be executed concurrently without blocking the main thread of execution. It's particularly useful for I/O-bound tasks, such as network requests or file operations.

Key concepts:
- Asynchronous functions (coroutines)
- Event loops
- Tasks
- Futures/Promises

## 2. Basic Async Concepts in Python

### 2.1 Defining an Async Function

```python
import asyncio

async def hello_world():
    print("Hello")
    await asyncio.sleep(1)
    print("World")

# Running the async function
asyncio.run(hello_world())
```

### 2.2 Creating and Awaiting Tasks

```python
async def main():
    task1 = asyncio.create_task(hello_world())
    task2 = asyncio.create_task(hello_world())
    
    await task1
    await task2

asyncio.run(main())
```

## 3. Async Parallelism Techniques

### 3.1 Gather for Parallel Execution

```python
import aiohttp
import asyncio

async def fetch_url(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()

async def main():
    urls = [
        'http://example.com',
        'http://example.org',
        'http://example.net'
    ]
    tasks = [asyncio.create_task(fetch_url(url)) for url in urls]
    results = await asyncio.gather(*tasks)
    for url, result in zip(urls, results):
        print(f"Content length of {url}: {len(result)}")

asyncio.run(main())
```

### 3.2 as_completed for Processing Results as They Arrive

```python
import asyncio
import random

async def random_sleep():
    sleep_time = random.uniform(0.1, 0.5)
    await asyncio.sleep(sleep_time)
    return sleep_time

async def main():
    tasks = [asyncio.create_task(random_sleep()) for _ in range(10)]
    
    for completed_task in asyncio.as_completed(tasks):
        result = await completed_task
        print(f"Task slept for {result:.2f} seconds")

asyncio.run(main())
```

## 4. Handling Errors in Async Code

### 4.1 Try-Except in Coroutines

```python
async def might_fail():
    if random.choice([True, False]):
        raise Exception("Random failure")
    return "Success"

async def main():
    try:
        result = await might_fail()
        print(result)
    except Exception as e:
        print(f"Caught an error: {e}")

asyncio.run(main())
```

### 4.2 Handling Errors with gather

```python
async def main():
    tasks = [asyncio.create_task(might_fail()) for _ in range(5)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for result in results:
        if isinstance(result, Exception):
            print(f"Task failed with error: {result}")
        else:
            print(f"Task succeeded with result: {result}")

asyncio.run(main())
```

## 5. Async Context Managers

```python
import asyncio
import aiofiles

async def write_to_file(filename, content):
    async with aiofiles.open(filename, mode='w') as file:
        await file.write(content)

async def main():
    tasks = [
        write_to_file('file1.txt', 'Hello'),
        write_to_file('file2.txt', 'World')
    ]
    await asyncio.gather(*tasks)

asyncio.run(main())
```

## 6. Combining Async with Multiprocessing

For CPU-bound tasks that need true parallelism:

```python
import asyncio
import multiprocessing
from concurrent.futures import ProcessPoolExecutor

def cpu_bound_task(x):
    return sum(i * i for i in range(x))

async def main():
    loop = asyncio.get_running_loop()
    with ProcessPoolExecutor() as pool:
        tasks = [
            loop.run_in_executor(pool, cpu_bound_task, 10**7),
            loop.run_in_executor(pool, cpu_bound_task, 10**7)
        ]
        results = await asyncio.gather(*tasks)
        print(results)

if __name__ == '__main__':
    asyncio.run(main())
```

## 7. Best Practices

1. Use `asyncio.create_task()` to schedule coroutines concurrently.
2. Avoid blocking calls in async code. Use async libraries or run_in_executor for unavoidable blocking operations.
3. Handle exceptions properly to prevent unhandled exceptions in tasks.
4. Use `asyncio.TimeoutError` and `asyncio.wait_for()` to implement timeouts.
5. Profile your async code to ensure it's providing the expected performance benefits.

