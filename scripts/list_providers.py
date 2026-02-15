import g4f
import g4f.Provider
print("All providers:")
for p in g4f.Provider.__providers__:
    if p.working:
        print(f" - {p.__name__}")
