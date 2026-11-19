"use client";

import React, { useMemo } from "react";
import katex from "katex";

interface MathKaTeXProps {
  math?: string;
  children?: string;
  block?: boolean;
  className?: string;
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

    // Check if the string contains LaTeX delimiters ($...$ or $$...$$)
    const hasDelimiters = content.includes("$");

    if (!hasDelimiters) {
      try {
        return katex.renderToString(content, {
          displayMode: block,
          throwOnError: false,
        });
      } catch {
        return content;
      }
    }

    // Replace $$...$$ with block math and $...$ with inline math
    let result = content;
    
    // First, process block math $$...$$
    result = result.replace(/\$\$([\s\S]*?)\$\$/g, (_, formula) => {
      try {
        return katex.renderToString(formula.trim(), {
          displayMode: true,
          throwOnError: false,
        });
      } catch {
        return `$$${formula}$$`;
      }
    });

    // Next, process inline math $...$
    result = result.replace(/\$([^\$\n\r]+?)\$/g, (_, formula) => {
      try {
        return katex.renderToString(formula.trim(), {
          displayMode: false,
          throwOnError: false,
        });
      } catch {
        return `$${formula}$`;
      }
    });

    return result;
  }, [content, block]);

  return (
    <span
      className={`katex-wrapper ${className}`}
      dangerouslySetInnerHTML={{ __html: renderedHtml }}
    />
  );
}
