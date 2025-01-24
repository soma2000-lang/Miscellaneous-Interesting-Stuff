## Smart Pointers

- Unique Pointers
- Shared Pointers
- Weak Pointers

Syntax of usage is similar as before: Due to operator overloading usage remains
same
```cpp
std::shared_ptr<string> p = std::make_shared<string>("Hello");
auto q = p;
p = nullptr;
if (q != nullptr) {
    std::cout << q->length() << *q << '\n';
}
```

```cpp
{
    T* ptr = new T;
    // ...
    delete ptr;
// its programmers responsibility to delete this pointer after usage.
// otherwise there will be memory leak

template<class T> 
class uniqute_ptr {
    T* p_ = nullptr;

    ~unique_ptr() {
        delete p_;    // deletion done automatically upon destruction
    }
}
}
```

- A raw pointer `T*` is copyable. If I copy, then which of us has now the
ownership. Who holds the responisibility of cleaning up? Both can't clear.

- Unique pointer is not copyable, it is only movable. When the move from A to B,
the move constructor nulls out the source pointer (maintains unique ownsership).

```cpp
// unique pointer is always a template of two parameters.
// second parameter is defaulted to std::default_delete<T>

template<class T, class Deleter = std::default_delete<T>>
class unique_ptr {
    T* p_ = nullptr;
    Deleter d_;

    ~unique_ptr() {
        if (p_) d_(p_); // called deleter on this pointer
    }
};

template<class T> 
struct default_delete {
    void operator()(T *p) comst {
        delete p; 
    }
}

// now we can use this to do some nice things

struct FileCloser {
    void operator() (FILE *fp) const {
        assert (fp != nullptr);
        fclose(fp);   // instead of delete we call close
    }
}

FILE *fp = fopen("input.txt", "r");
std::unique_ptr<FILE, FileCloser> uptr(fp);
```

#### Rule of thumb for smart pointers
- Treat smart pointer just like raw pointer types
    - Pass by value!
    - Return by value (of course)!
    - Passing a pointer by reference 
- A function taking a unique_ptr by value shows transfer of ownership

```cpp
#include <iostream>
#include <memory>

class MyClass {
public:
    MyClass() { std::cout << "MyClass constructor\n"; }
    ~MyClass() { std::cout << "MyClass destructor\n"; }
    void show() { std::cout << "Hello from MyClass\n"; }
};

// Function that takes unique_ptr by value (transfers ownership)
void takeOwnership(std::unique_ptr<MyClass> ptr) {
    std::cout << "Taking ownership\n";
    ptr->show();
}

int main() {
    std::unique_ptr<MyClass> myPtr = std::make_unique<MyClass>();

    // Pass unique_ptr by value to the function, transferring ownership
    takeOwnership(std::move(myPtr)); // myPtr is moved

    // At this point, myPtr is no longer valid
    if (!myPtr) {
        std::cout << "myPtr is now null\n";
    }

    return 0;
}
```
#### Shared Pointer
- syntax similar to the unique_ptr
- It expresses shared ownsership. Reference counting.

![](../assets/sharedPtr.png)
![](../assets/class.png)

`F`, `V` are base classes. `T` is a derived class. Pointers of base class pointing
to object of derived class. Both will be pointing to a different offset in the
heap allocated object.

![](../assets/sharedPtr2.png)






