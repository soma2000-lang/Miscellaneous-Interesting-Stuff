## Function Inlining

C++ FAQs: [Link](https://isocpp.org/wiki/faq/inline-functions)

Assuming that we already know about the ODR (One Definition Rule) and how 
marking a function inline helps that, lets discuss function inling from 
performance POV.

### Why Inlining

When the compiler inline-expands a function call, the function’s code gets 
inserted into the caller’s code stream.

When a program makes a function call, the instruction pointer (IP) jumps to a 
different memory address, executes the instructions at that location, and then 
jumps back to the original location.

This jumping to a new address can be inefficient because the next instruction 
to be executed may not be cached in the L1-I cache.

If the function is small, it often makes more sense for it to be inlined in the 
caller’s code stream. In such cases, there is no jump to an arbitrary location, 
and the L1-I cache remains warm.

Additionally, compilers are generally better suited to apply optimizations when 
the code is inlined, compared to optimizing across multiple distinct functions.


### Why not always inline
Inlining all function calls can lead to code bloat, increasing the size of the 
executable and potentially causing cache thrashing.

Consider a scenario in the hot path: before sending an order to the exchange, we 
perform a sanity check. If there is an error, we call the function logAndDebug, 
which handles some bookkeeping internally. In the typical case (the happy path), 
the order is sent to the exchange.

```cpp
bool isError = checkOrder(order);

if (isError) {
    logAndDebug(order);
} else {
    sendOrderToExchange(order);
}

```

Here, `isError` is rarely true, and the happy path is executed most of the time.

If the function `logAndDebug` were inlined, unnecessary instructions—executed only 
in rare cases—would occupy space in the instruction cache, potentially polluting 
it. This could slow down the program instead of improving performance.