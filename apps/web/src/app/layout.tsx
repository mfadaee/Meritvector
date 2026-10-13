import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "MeritVector",
  description: "Evidence-based workforce intelligence (synthetic demonstration)",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="font-sans antialiased" style={{ ["--font-sans" as string]: "Inter, ui-sans-serif, system-ui" }}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
