import ntpy


def main():
    print(f"Hello from {ntpy.__package__}({ntpy.__version__})! ")
    ntpy.t.x()


if __name__ == "__main__":
    main()
