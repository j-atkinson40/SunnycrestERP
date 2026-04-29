/**
 * HtmlEmailRenderer tests — Phase W-4b Layer 1 Step 4c.
 *
 * Coverage:
 *   - Renders sandboxed iframe with srcDoc + restrictive sandbox attr
 *   - Image-blocked banner appears when srcdoc carries data-blocked
 *   - "Show images" toggle swaps srcdoc to unblocked variant
 *   - Hide images toggle reverses
 *   - Iframe carries data-testid for selectability
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";


const BLOCKED_DOC = `<!DOCTYPE html>
<html><head>
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src cid: data:; style-src 'unsafe-inline'; font-src 'self' data:; frame-ancestors 'self';">
<style>img[data-external="true"][data-blocked="true"]{display:inline-block}</style>
</head><body>
<p>Hello</p>
<img src="https://x.com/i.png" data-external="true" data-blocked="true">
</body></html>`;

const NO_BLOCK_DOC = `<!DOCTYPE html>
<html><head>
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src cid: data:; style-src 'unsafe-inline'; font-src 'self' data:; frame-ancestors 'self';">
</head><body><p>cid only</p></body></html>`;


describe("HtmlEmailRenderer", () => {
  async function renderRenderer(
    srcdoc: string,
    initialShowImages = false,
  ) {
    const { default: HtmlEmailRenderer } = await import("./HtmlEmailRenderer");
    render(
      <HtmlEmailRenderer
        sandboxedSrcdoc={srcdoc}
        initialShowImages={initialShowImages}
      />,
    );
  }

  it("renders sandboxed iframe with restrictive sandbox attr", async () => {
    await renderRenderer(BLOCKED_DOC);
    const iframe = screen.getByTestId("email-html-iframe") as HTMLIFrameElement;
    expect(iframe).toBeInTheDocument();
    expect(iframe.tagName).toBe("IFRAME");
    expect(iframe.getAttribute("sandbox")).toBe("allow-same-origin");
  });

  it("iframe srcDoc carries CSP meta tag", async () => {
    await renderRenderer(BLOCKED_DOC);
    const iframe = screen.getByTestId("email-html-iframe") as HTMLIFrameElement;
    expect(iframe.getAttribute("srcdoc")).toContain(
      "Content-Security-Policy",
    );
  });

  it("renders image-blocked banner when blocked imgs present", async () => {
    await renderRenderer(BLOCKED_DOC);
    expect(
      screen.getByTestId("email-images-blocked-banner"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("email-show-images-btn")).toBeInTheDocument();
  });

  it("does not render banner when srcdoc has no blocked imgs", async () => {
    await renderRenderer(NO_BLOCK_DOC);
    expect(
      screen.queryByTestId("email-images-blocked-banner"),
    ).not.toBeInTheDocument();
  });

  it("Show images click swaps srcdoc to unblocked variant", async () => {
    const user = userEvent.setup();
    await renderRenderer(BLOCKED_DOC);
    const iframeBefore = screen.getByTestId(
      "email-html-iframe",
    ) as HTMLIFrameElement;
    expect(iframeBefore.getAttribute("srcdoc")).toContain(
      'data-blocked="true"',
    );

    await user.click(screen.getByTestId("email-show-images-btn"));

    const iframeAfter = screen.getByTestId(
      "email-html-iframe",
    ) as HTMLIFrameElement;
    // Body img should NOT carry data-blocked anymore
    const srcdoc = iframeAfter.getAttribute("srcdoc") || "";
    const bodyHtml = srcdoc.split("</head>")[1] || "";
    expect(bodyHtml).not.toContain('data-blocked="true"');
    // CSP loosened to permit https
    expect(srcdoc).toContain("img-src cid: data: https: http:;");
  });

  it("Hide images toggle reverses to blocked variant", async () => {
    const user = userEvent.setup();
    await renderRenderer(BLOCKED_DOC);
    await user.click(screen.getByTestId("email-show-images-btn"));
    expect(screen.getByTestId("email-hide-images-btn")).toBeInTheDocument();
    await user.click(screen.getByTestId("email-hide-images-btn"));
    const iframe = screen.getByTestId(
      "email-html-iframe",
    ) as HTMLIFrameElement;
    const bodyHtml = (iframe.getAttribute("srcdoc") || "").split("</head>")[1] || "";
    expect(bodyHtml).toContain('data-blocked="true"');
  });

  it("initialShowImages=true renders without banner", async () => {
    await renderRenderer(BLOCKED_DOC, true);
    expect(
      screen.queryByTestId("email-images-blocked-banner"),
    ).not.toBeInTheDocument();
    // Hide-images toggle visible because we know we're in show-images mode
    expect(screen.getByTestId("email-hide-images-btn")).toBeInTheDocument();
  });
});
