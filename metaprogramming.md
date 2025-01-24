## Template Metaprogramming

[Link to CPPCON Talk](https://youtu.be/Am2is2QCvxY?si=QrulPFBy7Dg5poQ1)

- Do work at compile time that otherwise would be done at Runtime.
- In C++, the template instantiation happens at the compile time, hence we make
use of it.
- For example if we call `f(x)` the compiler will manufacture(instantiate) the
function for us (assume f is a template here).
- It is not free, as the heavy work needs to be done at compile time which 
leads to increased compile time.
- Can't rely on runtime primitives like virtual functions, dynamic dispatch.
Keep things constant while metaprogramming.

1. **Absolute Value Metafunction**

```cpp
template<int N>
struct ABS {
    static constexpr int value = (N < 0) ? -N : N;
};
```

- A metafunction call: The arguments are passed through the template's 
arguments.
- `Call` syntax is a request for the template's static value.
- `const int ans = ABS<-142>::value;`

2. **Compile Time GCD**

Here we use compile time recursion. For base cases, we have to do pattern 
matching.

```cpp
template<int N, int M>
struct gcd {
    static constexpr int value = gcd<M, N % M>::value;
};

template<int N>
struct gcd<N, 0> {
    static_assert(N != 0);
    static constexpr int value = N;
};
```

3. **Metafunction can take a type as Parameter/Argument**
We can make a metafunction similar to `sizeof`

```cpp
// primary template handles scalar (non-array) types as base case:
template<class T> 
struct rank {
    static constexpr size_t value = 0u;
};

// partial specialization recognizes any array type:
template<class U, size_t N>
struct rank<U[N]> {
    static constexpr size_t value = 1 + rank<U>::value;
};

const int N = rank<int[2][1][4]>::value; // gives 3 at compile time
```

*Here we didn't recurse on the primary template, but did on the specialisation.*

4. **Type**
```cpp
#include <iostream>
#include <type_traits>

// A simple type trait to remove constness
template <typename T>
struct RemoveConst {
    using type = T;  // Default case: T is unchanged
};

template <typename T>
struct RemoveConst<const T> {
    using type = T;  // Specialized case: remove const qualifier
};

int main() {
    // Using the RemoveConst trait
    RemoveConst<const int>::type x = 42;  // 'RemoveConst<const int>::type' is equivalent to 'int'
    std::cout << "x = " << x << std::endl;
    
    return 0;
}
```

5. **Conditional Types during compile time**
```cpp
#include <iostream>
#include <stdexcept>


template<typename T>
struct type_is {
	using type = T;
};

// primary template assumes the bool value is true:
template<bool, typename T, typename Q>
struct conditional_type : type_is<T> {};

// partial specialization recognizes a false value:
template<typename T, typename Q>
struct conditional_type<false, T, Q> : type_is<Q> {};

int main() {
    constexpr bool q = false;
    conditional_type<q, int, double>::type s;
    std::cout << sizeof(s) << '\n';
    return 0;
}
```
`false_type` and `true_type` can have static value with F/T.

![](../assets/meta1.png)

How to deal with parameters pack:

![](../assets/meta2.png)

