//Next.js root layout component. This component wraps all pages and provides a consistent layout, including a sidebar navigation and main content area.

import "../styles/globals.css";
/**
 * Link is a React component provided by Next.js for navigation between pages.
 * Link supports optimized client-side navigation and route prefetching. This normally makes navigation faster and avoids reloading the entire webpage.
 */
import Sidebar from "../components/layout/Sidebar";
import SettingsSync from "../components/layout/SettingsSync";
/**
 * ReactNode is a TS type that represents any valid React child, including elements, strings, numbers, fragments, portals, and arrays of these types. 
 * React documents ReactNode as the union of the possible types that can be passed as JSX children.
 * The word type tells TypeScript: Import ReactNode only for type checking. It is not a JavaScript runtime value.
 * You use it here:{ children }: { children: ReactNode }  After TypeScript compiles the file into JavaScript, the ReactNode import is removed because JavaScript does not need TypeScript types.
 */
import type { ReactNode } from "react";

//defines website metadata that Next.js places in the HTML document metadata
export const metadata = {
  //The title normally appears in the browser tab
  title: "AI Life Execution",
  //The description may be used by search engines or link-preview systems to understand the page
  description: "Weekly planning, daily execution, study timer, and review loop.",
};

/**
 * Create the main Next.js layout component, receive the current page as children, and export this component as the file’s default export.
 * { children }: { children: ReactNode } is a TypeScript type annotation. It means: The component receives an object containing a children property, and children must be content that React can render(渲染).
 */
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <SettingsSync />
        <div className="app-shell">
          <Sidebar />
          {/* Render the current page content inside the <main> area. */}
          <main className="main-content">{children}</main>
        </div>
      </body>
    </html>
  );
}
