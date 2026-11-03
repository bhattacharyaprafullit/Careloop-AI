"use client";

import React, { createContext, useContext, useEffect, useState } from "react";

type Theme = "light" | "dark";

interface ThemeContextType {
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextType>({
  theme: "light",
  toggleTheme: () => {},
  setTheme: () => {},
});

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>("dark");

  useEffect(() => {
    const stored = (typeof window !== "undefined" ? localStorage.getItem("careloop-theme") : null) as Theme | null;
    if (stored === "light") {
      setThemeState("light");
      document.documentElement.classList.remove("dark");
    } else {
      // Default to Dark Mode on initial open!
      setThemeState("dark");
      document.documentElement.classList.add("dark");
      if (!stored && typeof window !== "undefined") {
        localStorage.setItem("careloop-theme", "dark");
      }
    }
  }, []);

  const setTheme = (newTheme: Theme) => {
    setThemeState(newTheme);
    if (typeof window !== "undefined") {
      localStorage.setItem("careloop-theme", newTheme);
      document.documentElement.classList.toggle("dark", newTheme === "dark");
    }
  };

  const toggleTheme = () => {
    setTheme(theme === "dark" ? "light" : "dark");
  };

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
