# Memory Reordering

### Some Background
Modern CPUs employ lots of techniques to counteract the latency cost of going 
to main memory.  These days CPUs can process hundreds of instructions in the 
time it takes to read or write data to the DRAM memory banks.

Memory access is generally the bottlenack.

Hardware caches are the most common tools used to hide this latency.
Unfortunately CPUs are now so fast that even these caches cannot keep up at 
times.  So to further hide this latency a number of less well known buffers 
are used. 

#### Lets understand about `store buffers` 

When a CPU executes a store operation it will try to write the data to the `L1 
cache` nearest to the CPU. If a cache miss occurs at this stage the CPU goes 
out to the next layer of cache. At this point on an Intel, and many other, 
CPUs a technique known as `write combining` comes into play. 

While the request for ownership of the L2 cache line is outstanding the data to 
be stored is written to one of a number of cache line sized buffers on the 
processor itself, known as `store buffers` on Intel CPUs.  These on chip 
buffers allow the CPU to continue processing instructions while the cache 
sub-system gets ready to receive and process the data.  The biggest advantage 
comes when the data is not present in any of the other cache layers.

These buffers become very interesting when subsequent writes happen to require 
the same cache line.  The subsequent writes can be combined into the buffer 
before it is committed down the cache hierarchy.

> What happens if the program wants to read some of the data that has been 
written to a buffer?  Well our hardware friends have thought of that and they 
will snoop the buffers before they read the caches.

![](../assets/store_buffer.png)

*Loads and stores to the caches and main memory are buffered and re-ordered 
using the load, store, and write-combining buffers.  These buffers are 
associative queues that allow fast lookup.  This lookup is necessary when a 
later load needs to read the value of a previous store that has not yet reached 
the cache.*

### Fencing

When a program is executed it does not matter if its instructions are 
re-ordered provided the same end result is achieved. For example, within a loop 
it does not matter when the loop counter is updated if no operation within the 
loop uses it.  
The compiler and CPU are free to re-order the instructions to best utilise the 
CPU provided it is updated by the time the next iteration is about to 
commence.  
Also over the execution of a loop this variable may be stored in a register and 
never pushed out to cache or main memory, thus it is never visible to another 
CPU.

> We use `volatile` keyword to tell the compiler that don't store this variable
in register. Always push down the changes to memory. So that other CPU can 
always see the latest value.

Provided “program order” is preserved the CPU, and compiler, are free to do 
whatever they see fit to improve performance.




### Hardware Memory Ordering in x86 Processors

The term memory ordering refers to the order in which the processor issues 
reads (loads) and writes (stores) through the system bus to system memory.

For example, the Intel386 processor enforces program ordering 
(generally referred to as strong ordering), where reads and writes are issued 
on the system in the order they occur in the instruction stream.

But the hardware may reorder the instructions for some optimizations. Sometimes
reads could go ahead of buffered writes.

<mark> Reads may be reordered with older writes to different memory locations 
but not with older writes to same memory location.</mark>

That is, if we write to location 1 and read from location 2, then the read from
location 2 could become globally visible before write to location 1.

```
let x = y = 0

processor 0                     processor 1
x = 1                           y = 1
print y                         print x

output = (0, 0) is possible
```

<mark> Stores are usually buffered before being sent to memory (L1 cache). We 
prioritise loads more than stores. Since they are on critical path. The instructions
are waiting for the data to be loaded before they can run. 
Although if a store followed by a load are for same memory location then we will
definitely follow program order.</mark>

### Software Reordering
Compiler can also sometimes reorder instructions in our program for optimizations.
For example, store to 2 different memory locations can be reordered by our
compiler.

### Avoid memory reordering
In a multi-threaded environment techniques need to be employed for making 
program results visible in a timely manner.
The techniques for making memory visible from a processor core are known as 
memory barriers or fences.

Memory barriers provide two properties.  Firstly, they preserve externally 
visible program order by ensuring all instructions either side of the barrier 
appear in the correct program order if observed from another CPU and, secondly, 
they make the memory visible by ensuring the data is propagated to the cache 
sub-system.

#### Asking compiler not to reorder
`asm volatile("" : : : "memory");` Fake instruction that asks compiler to not
reorder any memory instruction around this barrier. A hint to compiler that 
whole of the memory can be touched by this instruction: hence don't do any
reordering. 

*In this case the hardware can still reorder instructions, even though we asked
our compiler to not reorder! Hence we will have to use hardware barriers.*

```cpp
#include <emmintrin.h>
void _mm_mfence (void) // Use this instruction as a barrier to prevent re-ordering in the hardware!
```

Perform serializing operation on all `load-from-memory` and `store-to-memory` 
instructions that were issued prior to this instruction. 
Guarantees that every memory access that precedes, in program order the memory 
fence instruction is globally visible before any memory instruction which 
follows the fence in program order.

*It drains the `store buffer`, before any following `loads` can go into memory.*

### Performance Impact of Memory Barriers

Memory barriers prevent a CPU from performing a lot of techniques to hide 
memory latency therefore they have a significant performance cost which must be 
considered.  To achieve maximum performance it is best to model the problem so 
the processor can do units of work, then have all the necessary memory barriers 
occur on the boundaries of these work units

## C++ Memory Model

- [Memory Model Article](https://dev.to/kprotty/understanding-atomics-and-memory-ordering-2mom)
- [Post on Stack Overflow](https://stackoverflow.com/questions/12346487/what-do-each-memory-order-mean)


