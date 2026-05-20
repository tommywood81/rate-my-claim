import { Lora, Libre_Franklin } from "next/font/google";

/** Body: OWID uses Libre Franklin. */
export const bodyFont = Libre_Franklin({
  subsets: ["latin"],
  variable: "--font-body",
  display: "swap",
});

/** Headlines: OWID uses a serif for hero and article titles. */
export const displayFont = Lora({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});
