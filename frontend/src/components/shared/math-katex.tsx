"use client";

import React, { useMemo } from "react";
import katex from "katex";

interface MathKaTeXProps {
  math?: string;
  children?: string;
  block?: boolean;
  className?: string;
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

export function MathKaTeX({
  math,
  children,
  block = false,
  className = "",
}: MathKaTeXProps) {
  const content = math || children || "";

  const renderedHtml = useMemo(() => {
    if (!content) return "";

    const hasDelimiters = content.includes("$");

    // If no $ delimiters, check if it's a raw LaTeX expression
    if (!hasDelimiters) {
      // If it looks like LaTeX (starts with backslash or math prop explicitly passed)
      if (math !== undefined || content.includes("\\") || content.includes("^") || content.includes("_")) {
        try {
          return katex.renderToString(content, {
            displayMode: block,
            throwOnError: false,
            trust: false,
          });
        } catch {
          return escapeHtml(content);
        }
      }
      // Otherwise it's pure plain text, escape HTML to prevent XSS
      return escapeHtml(content);
    }

    // Split text by block math $$...$$ and inline math $...$
    // preserving delimiters for token classification
    const tokens = content.split(/(\$\$[\s\S]*?\$\$|\$[^\$\n\r]+?\$)/g);

    return tokens
      .map((token) => {
        if (!token) return "";

        // Block math $$...$$
        if (token.startsWith("$$") && token.endsWith("$$")) {
          const formula = token.slice(2, -2).trim();
          try {
            return katex.renderToString(formula, {
              displayMode: true,
              throwOnError: false,
              trust: false,
            });
          } catch {
            return `$$${escapeHtml(formula)}$$`;
          }
        }

        // Inline math $...$
        if (token.startsWith("$") && token.endsWith("$")) {
          const formula = token.slice(1, -1).trim();
          try {
            return katex.renderToString(formula, {
              displayMode: false,
              throwOnError: false,
              trust: false,
            });
          } catch {
            return `$${escapeHtml(formula)}$`;
          }
        }

        // Regular non-math text: strictly escape HTML
        return escapeHtml(token);
      })
      .join("");
  }, [content, block, math]);

  return (
    <span
      className={`katex-wrapper ${className}`}
      dangerouslySetInnerHTML={{ __html: renderedHtml }}
    />
  );
}
