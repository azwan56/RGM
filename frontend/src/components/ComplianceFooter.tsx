export default function ComplianceFooter() {
  return (
    <footer className="w-full border-t border-[var(--rgm-border)] bg-[var(--rgm-bg)]/80 py-5 px-4 text-center text-xs text-[var(--rgm-text-muted)]">
      <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-center gap-2 sm:gap-4">
        <span>© 2026 万跑科技（上海）有限公司.</span>
        <a
          href="https://beian.miit.gov.cn/"
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-[var(--rgm-text)] transition underline-offset-2 hover:underline"
        >
          [沪ICP备2026018807]
        </a>
        <div className="flex items-center gap-3">
          <a
            href="/privacy"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-[var(--rgm-text)] transition"
          >
            隐私政策
          </a>
          <span>·</span>
          <a
            href="/citations"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-[var(--rgm-text)] transition"
          >
            运动科学参考文献与免责声明
          </a>
        </div>
      </div>
    </footer>
  );
}
