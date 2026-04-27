# Sprint 2 - Salma Essamiri: Tkinter GUI — login, facility browser, booking form

"""
Sprint 3 | gui/app.py
Tkinter desktop GUI — SE2 Grade 4: user GUI + database connection.
Provides login, facility browser, and booking creation screens.
Commit: Mohab – Sprint 3
"""

import threading
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import messagebox, ttk
from typing import List, Optional

from client.sfbs_client import SFBSClient


# ─────────────────────────────────────────────────────────────────────────── #
#  LoginView                                                                  #
# ─────────────────────────────────────────────────────────────────────────── #

class LoginView(tk.Frame):

    def __init__(self, master: tk.Tk, on_login_success) -> None:
        super().__init__(master, padx=40, pady=40, bg="#f5f5f5")
        self._on_success = on_login_success
        self._build()

    def _build(self) -> None:
        tk.Label(self, text="SFBS Login", font=("Helvetica", 20, "bold"),
                 bg="#f5f5f5", fg="#2c3e50").pack(pady=(0, 20))

        form = tk.Frame(self, bg="#f5f5f5")
        form.pack()

        tk.Label(form, text="Username:", bg="#f5f5f5").grid(row=0, column=0, sticky="e", pady=5)
        self._username = tk.Entry(form, width=28)
        self._username.grid(row=0, column=1, padx=8)

        tk.Label(form, text="Password:", bg="#f5f5f5").grid(row=1, column=0, sticky="e", pady=5)
        self._password = tk.Entry(form, width=28, show="*")
        self._password.grid(row=1, column=1, padx=8)

        self._status = tk.Label(self, text="", fg="red", bg="#f5f5f5")
        self._status.pack(pady=5)

        btn = tk.Button(self, text="Log In", width=16, bg="#3498db", fg="white",
                        relief="flat", font=("Helvetica", 11),
                        command=self._do_login)
        btn.pack(pady=10)
        self._password.bind("<Return>", lambda _: self._do_login())

    def _do_login(self) -> None:
        username = self._username.get().strip()
        password = self._password.get().strip()
        if not username or not password:
            self._status.config(text="Please fill in all fields.")
            return
        self._status.config(text="Logging in…", fg="#7f8c8d")
        self.update()
        self._on_success(username, password)


# ─────────────────────────────────────────────────────────────────────────── #
#  FacilityView                                                               #
# ─────────────────────────────────────────────────────────────────────────── #

class FacilityView(tk.Frame):

    def __init__(self, master: tk.Widget, client: SFBSClient,
                 on_book: callable) -> None:
        super().__init__(master, bg="#f5f5f5")
        self._client  = client
        self._on_book = on_book
        self._facilities: List[dict] = []
        self._build()

    def _build(self) -> None:
        header = tk.Frame(self, bg="#2c3e50", pady=10)
        header.pack(fill="x")
        tk.Label(header, text="Available Facilities", font=("Helvetica", 14, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=15)
        tk.Button(header, text="⟳ Refresh", bg="#2980b9", fg="white",
                  relief="flat", command=self.refresh).pack(side="right", padx=10)

        cols = ("Name", "Type", "Capacity", "Rate (PLN/h)", "Status")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=12)
        for col in cols:
            self._tree.heading(col, text=col)
            self._tree.column(col, width=130)
        self._tree.pack(fill="both", expand=True, padx=10, pady=10)

        scrollbar = ttk.Scrollbar(self, orient="vertical",
                                  command=self._tree.yview)
        self._tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        tk.Button(self, text="Book Selected Facility", bg="#27ae60", fg="white",
                  font=("Helvetica", 11), relief="flat",
                  command=self._book_selected).pack(pady=10)

        self.refresh()

    def refresh(self) -> None:
        def _load():
            facilities = self._client.get_facilities(available_only=True)
            self._facilities = facilities
            self._tree.delete(*self._tree.get_children())
            for f in facilities:
                self._tree.insert("", "end", iid=f["id"], values=(
                    f.get("name", ""),
                    f.get("facility_type", ""),
                    f.get("capacity", ""),
                    f"${f.get('hourly_rate', 0):.2f}",
                    f.get("status", ""),
                ))
        threading.Thread(target=_load, daemon=True).start()

    def _book_selected(self) -> None:
        selected = self._tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a facility first.")
            return
        facility_id = selected[0]
        facility = next((f for f in self._facilities if f["id"] == facility_id), None)
        if facility:
            self._on_book(facility)


# ─────────────────────────────────────────────────────────────────────────── #
#  BookingView                                                                #
# ─────────────────────────────────────────────────────────────────────────── #

class BookingView(tk.Toplevel):

    def __init__(self, master: tk.Widget, client: SFBSClient,
                 facility: dict) -> None:
        super().__init__(master)
        self._client   = client
        self._facility = facility
        self.title(f"Book: {facility['name']}")
        self.geometry("420x380")
        self.resizable(False, False)
        self.configure(bg="#f5f5f5")
        self._build()

    def _build(self) -> None:
        tk.Label(self, text=f"Booking: {self._facility['name']}",
                 font=("Helvetica", 14, "bold"), bg="#f5f5f5",
                 fg="#2c3e50").pack(pady=15)

        info = tk.Frame(self, bg="#f5f5f5")
        info.pack(padx=20, fill="x")
        tk.Label(info, text=f"Rate: ${self._facility.get('hourly_rate', 0):.2f}/h",
                 bg="#f5f5f5", font=("Helvetica", 11)).pack(anchor="w")
        tk.Label(info, text=f"Capacity: {self._facility.get('capacity', '')}",
                 bg="#f5f5f5").pack(anchor="w")

        form = tk.Frame(self, bg="#f5f5f5", pady=10)
        form.pack(padx=20, fill="x")

        now   = datetime.now()
        start = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        end   = start + timedelta(hours=2)

        tk.Label(form, text="Start (YYYY-MM-DD HH:MM):", bg="#f5f5f5").grid(
            row=0, column=0, sticky="w", pady=4)
        self._start_var = tk.StringVar(value=start.strftime("%Y-%m-%d %H:%M"))
        tk.Entry(form, textvariable=self._start_var, width=22).grid(
            row=0, column=1, padx=8)

        tk.Label(form, text="End   (YYYY-MM-DD HH:MM):", bg="#f5f5f5").grid(
            row=1, column=0, sticky="w", pady=4)
        self._end_var = tk.StringVar(value=end.strftime("%Y-%m-%d %H:%M"))
        tk.Entry(form, textvariable=self._end_var, width=22).grid(
            row=1, column=1, padx=8)

        tk.Label(form, text="Notes:", bg="#f5f5f5").grid(
            row=2, column=0, sticky="w", pady=4)
        self._notes = tk.Entry(form, width=22)
        self._notes.grid(row=2, column=1, padx=8)

        self._status = tk.Label(self, text="", fg="red", bg="#f5f5f5")
        self._status.pack()

        tk.Button(self, text="Confirm Booking", bg="#27ae60", fg="white",
                  font=("Helvetica", 11), relief="flat", width=18,
                  command=self._confirm).pack(pady=15)

    def _confirm(self) -> None:
        try:
            start = datetime.strptime(self._start_var.get().strip(), "%Y-%m-%d %H:%M")
            end   = datetime.strptime(self._end_var.get().strip(), "%Y-%m-%d %H:%M")
        except ValueError:
            self._status.config(text="Invalid date format. Use YYYY-MM-DD HH:MM")
            return
        if end <= start:
            self._status.config(text="End time must be after start time.")
            return

        self._status.config(text="Creating booking…", fg="#7f8c8d")
        self.update()

        def _do():
            result = self._client.create_booking(
                self._facility["id"], start, end, self._notes.get()
            )
            if result:
                messagebox.showinfo("Success",
                    f"Booking confirmed!\nTotal: ${result.get('total_amount', 0):.2f}")
                self.destroy()
            else:
                self._status.config(text="Booking failed. Try again.", fg="red")

        threading.Thread(target=_do, daemon=True).start()


# ─────────────────────────────────────────────────────────────────────────── #
#  DashboardView                                                              #
# ─────────────────────────────────────────────────────────────────────────── #

class DashboardView(tk.Frame):

    def __init__(self, master: tk.Widget, client: SFBSClient,
                 username: str) -> None:
        super().__init__(master, bg="#ecf0f1")
        self._client   = client
        self._username = username
        self._build()

    def _build(self) -> None:
        nav = tk.Frame(self, bg="#2c3e50", pady=8)
        nav.pack(fill="x")
        tk.Label(nav, text=f"  SFBS  |  {self._username}",
                 font=("Helvetica", 13, "bold"), bg="#2c3e50",
                 fg="white").pack(side="left")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=5, pady=5)

        facility_tab = FacilityView(nb, self._client, self._open_booking)
        nb.add(facility_tab, text="  Facilities  ")

        booking_tab = self._build_my_bookings(nb)
        nb.add(booking_tab, text="  My Bookings  ")

    def _build_my_bookings(self, parent) -> tk.Frame:
        frame = tk.Frame(parent, bg="#f5f5f5")
        cols  = ("ID", "Facility", "Amount", "Status", "Created")
        tree  = ttk.Treeview(frame, columns=cols, show="headings", height=14)
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=140)
        tree.pack(fill="both", expand=True, padx=10, pady=10)
        self._bookings_tree = tree

        tk.Button(frame, text="⟳ Refresh Bookings", bg="#3498db", fg="white",
                  relief="flat", command=lambda: self._load_bookings(tree)).pack()
        self._load_bookings(tree)
        return frame

    def _load_bookings(self, tree: ttk.Treeview) -> None:
        def _do():
            bookings = self._client.get_bookings()
            tree.delete(*tree.get_children())
            for b in bookings:
                tree.insert("", "end", values=(
                    b.get("id", "")[:8] + "…",
                    b.get("facility_id", "")[:8] + "…",
                    f"${b.get('total_amount', 0):.2f}",
                    b.get("status", ""),
                    b.get("created_at", "")[:10],
                ))
        threading.Thread(target=_do, daemon=True).start()

    def _open_booking(self, facility: dict) -> None:
        BookingView(self, self._client, facility)


# ─────────────────────────────────────────────────────────────────────────── #
#  Main Application                                                           #
# ─────────────────────────────────────────────────────────────────────────── #

class SFBSApp:
    """
    Root Tkinter application.
    Manages the window and switches between Login and Dashboard frames.
    """

    def __init__(self, server_url: str = "http://localhost:8000") -> None:
        self._root   = tk.Tk()
        self._root.title("Sport Facility Booking System")
        self._root.geometry("800x560")
        self._root.configure(bg="#f5f5f5")
        self._client = SFBSClient(base_url=server_url)
        self._client.start()
        self._current_frame: Optional[tk.Frame] = None
        self._show_login()

    def _show_login(self) -> None:
        self._switch_to(LoginView(self._root, self._do_login))

    def _do_login(self, username: str, password: str) -> None:
        def _attempt():
            token = self._client.login(username, password)
            if token:
                self._root.after(0, lambda: self._show_dashboard(username))
            else:
                self._root.after(0, lambda: messagebox.showerror(
                    "Login Failed", "Invalid username or password."))
        threading.Thread(target=_attempt, daemon=True).start()

    def _show_dashboard(self, username: str) -> None:
        self._switch_to(DashboardView(self._root, self._client, username))

    def _switch_to(self, frame: tk.Frame) -> None:
        if self._current_frame:
            self._current_frame.destroy()
        self._current_frame = frame
        self._current_frame.pack(fill="both", expand=True)

    def run(self) -> None:
        self._root.mainloop()
        self._client.stop()


if __name__ == "__main__":
    SFBSApp().run()
