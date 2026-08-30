"""杏吧版块定义（fid → slug）。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class XingbaForum:
    fid: int
    name: str
    slug: str

    @property
    def list_path(self) -> str:
        return (
            f"/forum.php?mod=forumdisplay&fid={self.fid}"
            f"&filter=lastpost&orderby=lastpost"
        )


XINGBA_FORUMS: tuple[XingbaForum, ...] = (
    XingbaForum(798, "杏吧华人下载区", "xingba-forum-798"),
    XingbaForum(280, "杏吧华人精品区", "xingba-forum-280"),
    XingbaForum(233, "杏吧高清新片区", "xingba-forum-233"),
    XingbaForum(103, "杏吧网盘下载区", "xingba-forum-103"),
    XingbaForum(723, "杏吧无码BT原创区", "xingba-forum-723"),
    XingbaForum(96, "杏吧亚洲无码区", "xingba-forum-96"),
    XingbaForum(70, "杏吧中文字幕区", "xingba-forum-70"),
    XingbaForum(232, "杏吧特邀新片区", "xingba-forum-232"),
    XingbaForum(135, "杏吧欧美区", "xingba-forum-135"),
    XingbaForum(525, "杏吧欧美BT区", "xingba-forum-525"),
    XingbaForum(134, "杏吧亚洲有码区", "xingba-forum-134"),
    XingbaForum(713, "杏吧有码BT原创区", "xingba-forum-713"),
)

XINGBA_FORUM_BY_SLUG = {f.slug: f for f in XINGBA_FORUMS}
XINGBA_FORUM_BY_FID = {f.fid: f for f in XINGBA_FORUMS}
