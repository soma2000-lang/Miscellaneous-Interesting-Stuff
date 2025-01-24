## `i++` vs `++i`

First lets see for our class how can we overload, the ++prefix and postfix++
operators.

```cpp
class Number {
public:
  Number& operator++ ();    // ++prefix
  Number  operator++ (int); // postfix++
};
```

*Note the different return types: the prefix version returns by reference, the
postfix version by value.*

```cpp
Number& Number::operator++ ()
{
  // do some logic here to increment
  return *this;
}

Number Number::operator++ (int)
{
  Number ans = *this;
  ++(*this);  // or just call operator++()
  return ans;
}
```

### Which is more efficient: `i++` or `++i`?

- `++i` is sometimes faster than, and is never slower than, `i++`.

- For intrinsic types like `int`, it doesn’t matter: `++i` and `i++` are the 
same speed. For Number class (above example), `++i` very well might be faster 
than `i++` since the latter might make a copy of the this object.
