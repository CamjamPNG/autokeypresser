import sys


def main():
    import tkinter as tk

    try:
        from autoclicker.app import AutoClickerApp
    except ImportError as exc:  # pragma: no cover
        import tkinter.messagebox as messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Missing dependency",
            "Required libraries are missing. Install them with:\n\n"
            "    pip install -r requirements.txt\n\n"
            f"Details: {exc}",
        )
        root.destroy()
        return 1

    root = tk.Tk()
    AutoClickerApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
