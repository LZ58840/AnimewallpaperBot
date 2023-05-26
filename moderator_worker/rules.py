import logging
import re
from asyncio import Event, create_task, gather, wait_for, TimeoutError
from datetime import datetime

from utils import async_database_ctx, normal_round, get_rabbitmq_auth, get_mysql_auth, get_reddit_auth
import time

from asyncpraw.models import Submission
from asyncpraw import Reddit
from celery import Celery
from monthdelta import monthmod


class Rule:
    removal_comment: str
    mysql_auth: dict[str, str]

    def __init__(self, mysql_auth):
        self.mysql_auth = mysql_auth

    async def evaluate(self, **kwargs) -> str | None:
        raise NotImplementedError


class ResolutionAny(Rule):
    resolution_tag_regex_str = r"[(\[]\s?([0-9]{3,})\s?[Xx×]\s?([0-9]{3,})\s?[)\]]"
    removal_comment = ("\n\n- **Missing resolution in title.** "
                       "Please state the exact resolution of your image in the submission title, "
                       "enclosed in (parentheses) or [brackets]. If you are submitting a collection, "
                       "ensure all unique resolutions are tagged separately.")

    async def evaluate(self, submission: Submission, removal_flag: Event, warning_flag: Event, enabled: bool):
        if not enabled:
            return
        if re.search(self.resolution_tag_regex_str, submission.title) is None:
            removal_flag.set()
            return self.removal_comment


class ResolutionMismatch(Rule):
    resolution_tag_regex_str = r"[(\[]\s?([0-9]{3,})\s?[Xx×]\s?([0-9]{3,})\s?[)\]]"
    removal_comment = ("\n\n- **Mismatched resolution{many} in title.** "
                       "Please ensure the resolution{many} tagged in the title exactly match{single} "
                       "the resolution{many} of your submitted image{many}.\n"
                       "\n\t- Tagged resolution{many} in title: {tagged}\n\n\t- Mismatched resolution{many}: {mismatched}")

    async def evaluate(self, submission: Submission, removal_flag: Event, warning_flag: Event, enabled: bool):
        if not enabled:
            return
        matches = re.findall(self.resolution_tag_regex_str, submission.title)
        tagged_resolutions = [(int(match[0]), int(match[1])) for match in matches]
        if len(tagged_resolutions) == 0:
            return
        async with async_database_ctx(self.mysql_auth) as db:
            query = ('SELECT i.id, i.width, i.height, (i.width,i.height) IN (%s) AS tagged '
                     'FROM submissions s JOIN images i ON s.id = i.submission_id WHERE s.id='
                     % ','.join(str(resolution) for resolution in tagged_resolutions))
            await db.execute(query + '%s', submission.id)
            rows = await db.fetchall()
        mismatched_resolutions = [(row['width'], row['height']) for row in rows if not row['tagged']]
        if len(mismatched_resolutions) > 0:
            removal_flag.set()
            many = 's' if len(tagged_resolutions) > 1 else ''
            single = 'es' if len(tagged_resolutions) == 1 else ''
            tagged = ", ".join(f"{resolution[0]}x{resolution[1]}" for resolution in tagged_resolutions)
            mismatched = ", ".join(f"{resolution[0]}x{resolution[1]}" for resolution in mismatched_resolutions)
            return self.removal_comment.format(many=many, single=single, tagged=tagged, mismatched=mismatched)


class ResolutionBad(Rule):
    removal_comment = "\n\n- **Bad resolution.**{h_section}{v_section}{s_section}"
    section_template = ("\n\n\t- {orientation} images must be at least **{width}x{height}**.\n"
                        "\n\t\t- {bad_images} {many} too small.")
    image_template = "[Image #{i} ({width}x{height})]({url})"

    async def evaluate(self,
                       submission: Submission,
                       removal_flag: Event,
                       warning_flag: Event,
                       enabled: bool,
                       horizontal: str = None,
                       vertical: str = None,
                       square: str = None):
        if not enabled:
            return
        h_threshold = self._parse_resolution_str(horizontal)
        v_threshold = self._parse_resolution_str(vertical)
        s_threshold = self._parse_resolution_str(square)
        async with async_database_ctx(self.mysql_auth) as db:
            await db.execute("SELECT res.id, res.orientation, res.width, res.height, res.url "
                             "FROM (SELECT i.id, "
                             "IF(i.width > i.height, 'horizontal', IF(i.width < i.height, 'vertical', 'square')) "
                             "AS orientation, i.width, i.height, i.url "
                             "FROM submissions s JOIN images i ON s.id = i.submission_id WHERE s.id=%s) res "
                             "WHERE res.orientation='horizontal' AND (res.width < %s OR res.height < %s) "
                             "OR res.orientation='vertical' AND (res.width < %s OR res.height < %s) "
                             "OR res.orientation='square' AND (res.width < %s OR res.height < %s) "
                             "ORDER BY res.id",
                             (submission.id, *h_threshold, *v_threshold, *s_threshold))
            rows = await db.fetchall()
        if len(rows) > 0:
            removal_flag.set()
            h_section = self._format_section('horizontal', h_threshold, rows)
            v_section = self._format_section('vertical', v_threshold, rows)
            s_section = self._format_section('square', s_threshold, rows)
            return self.removal_comment.format(
                h_section=h_section,
                v_section=v_section,
                s_section=s_section
            )

    @staticmethod
    def _parse_resolution_str(resolution_str) -> tuple[int, int] | tuple[None, None]:
        if resolution_str is not None:
            split_resolution_str = resolution_str.split("x")
            return int(split_resolution_str[0]), int(split_resolution_str[1])
        return None, None

    def _format_section(self, orientation, threshold, bad_images_rows):
        bad_images = [i for i in range(len(bad_images_rows)) if bad_images_rows[i]['orientation'] == orientation]
        if threshold == (None, None) or len(bad_images) == 0:
            return ""
        bad_images_str = ', '.join(
            self.image_template.format(
                i=i + 1,
                width=bad_images_rows[i]['width'],
                height=bad_images_rows[i]['height'],
                url=bad_images_rows[i]['url']
            )
            for i in bad_images
        )
        many = 'are' if len(bad_images) != 1 else 'is'
        return self.section_template.format(
            orientation=orientation.capitalize(),
            width=threshold[0],
            height=threshold[1],
            bad_images=bad_images_str,
            many=many
        )


class AspectRatioBad(Rule):
    removal_comment = "\n\n- **Bad aspect ratio.**{h_section}{v_section}"
    section_template = "\n\n\t- {orientation} images must have an aspect ratio **{threshold}**."
    deficiency_template = "\n\n\t\t- {bad_images} {many} too {deficiency}."
    image_template = "[Image #{i} ({ratio}:1)]({url})"

    async def evaluate(self,
                       submission: Submission,
                       removal_flag: Event,
                       warning_flag: Event,
                       enabled: bool,
                       horizontal: str = None,
                       vertical: str = None):
        if not enabled:
            return
        h_thresholds = self._parse_threshold(horizontal)
        v_thresholds = self._parse_threshold(vertical)
        args = (
            h_thresholds['tall'][2],
            h_thresholds['wide'][2],
            v_thresholds['tall'][2],
            v_thresholds['wide'][2],
            submission.id
        )
        async with async_database_ctx(self.mysql_auth) as db:
            await db.execute("SELECT ar.id, ar.orientation, ar.ratio, ar.url,"
                             "IF(ar.orientation='horizontal', "
                             "IF(ar.ratio < %s, 'tall', IF(ar.ratio > %s, 'wide', NULL)), "
                             "IF(ar.orientation='vertical', "
                             "IF(ar.ratio < %s, 'tall', IF(ar.ratio > %s, 'wide', NULL)), NULL)) as result "
                             "FROM (SELECT i.id, "
                             "IF(i.width > i.height, 'horizontal', IF(i.width < i.height, 'vertical', 'square')) "
                             "AS orientation, ROUND(i.width / i.height, 3) AS ratio, i.url "
                             "FROM submissions s JOIN images i ON s.id = i.submission_id "
                             "WHERE s.id=%s ORDER BY i.id) ar "
                             "HAVING result IS NOT NULL", args)
            rows = await db.fetchall()
        if len(rows) > 0:
            removal_flag.set()
            bad_image_dict = {
                "horizontal": {"tall": [], "wide": []},
                "vertical": {"tall": [], "wide": []},
            }
            for i in range(len(rows)):
                bad_image_dict[rows[i]['orientation']][rows[i]['result']].append(i)
            h_section = self._format_section('horizontal', h_thresholds, bad_image_dict, rows)
            v_section = self._format_section('vertical', v_thresholds, bad_image_dict, rows)
            return self.removal_comment.format(
                h_section=h_section,
                v_section=v_section,
            )

    def _format_section(self, orientation, threshold, bad_image_dict, bad_images_rows):
        threshold_str = self._threshold_to_comment(threshold)
        if threshold_str == "" or len(bad_image_dict[orientation]['tall']) == len(bad_image_dict[orientation]['wide']) == 0:
            return ""
        tall_images_str = ', '.join(
            self.image_template.format(
                i=i + 1,
                ratio=bad_images_rows[i]['ratio'],
                url=bad_images_rows[i]['url']
            )
            for i in bad_image_dict[orientation]['tall']
        )
        tall_images_many = "are" if len(bad_image_dict[orientation]['tall']) != 1 else "is"
        tall_images_section = self.deficiency_template.format(bad_images=tall_images_str, many=tall_images_many, deficiency='tall') if len(bad_image_dict[orientation]['tall']) > 0 else ""
        wide_images_str = ', '.join(
            self.image_template.format(
                i=i + 1,
                ratio=bad_images_rows[i]['ratio'],
                url=bad_images_rows[i]['url']
            )
            for i in bad_image_dict[orientation]['wide']
        )
        wide_images_many = "are" if len(bad_image_dict[orientation]['wide']) != 1 else "is"
        wide_images_section = self.deficiency_template.format(bad_images=wide_images_str, many=wide_images_many, deficiency='wide') if len(bad_image_dict[orientation]['wide']) > 0 else ""
        return (self.section_template.format(orientation=orientation.capitalize(), threshold=threshold_str)
                + tall_images_section
                + wide_images_section)

    @staticmethod
    def _threshold_to_comment(threshold: dict[str, tuple[int, int, float]]) -> str:
        if threshold['tall'][2] is not None and threshold['wide'][2] is not None:
            return (f"between {threshold['tall'][0]}:{threshold['tall'][1]} ({threshold['tall'][2]}:1) "
                    f"and {threshold['wide'][0]}:{threshold['wide'][1]} ({threshold['wide'][2]}:1)")
        elif threshold['tall'][2] is not None:
            return f"of or wider than {threshold['tall'][0]}:{threshold['tall'][1]} ({threshold['tall'][2]}:1)"
        elif threshold['wide'][2] is not None:
            return f"of or taller than {threshold['wide'][0]}:{threshold['wide'][1]} ({threshold['wide'][2]}:1)"
        return ""

    def _parse_threshold(self, threshold_str):
        if threshold_str is None:
            return {"tall": (None, None, None), "wide": (None, None, None)}
        got_threshold_str = threshold_str.split(" to ")[:2]
        got_ratios = (self._parse_ratio_str(got_threshold_str[0]), self._parse_ratio_str(got_threshold_str[1]))
        return {"tall": got_ratios[0], "wide": got_ratios[1]}

    @staticmethod
    def _parse_ratio_str(ratio_str) -> tuple[int, int, float] | tuple[None, None, None]:
        try:
            a_to_b = ratio_str.split(":")[:2]
            return int(a_to_b[0]), int(a_to_b[1]), normal_round(int(a_to_b[0]) / int(a_to_b[1]), 3)
        except (ZeroDivisionError, ValueError):
            return None, None, None


class SourceCommentAny(Rule):
    removal_comment = "\n\n- **Missing source in comments.** Timeout after {timeout} hour{many}."
    description = ("\n\n\t- Please make a top level comment crediting the original source artwork/artist."
                   "\n\n\t\t- Try doing a search for the artwork on "
                   "[SauceNAO](https://saucenao.com/) or [IQDB](https://iqdb.org/?css=1)."
                   "\n\n\t\t- If you edited this wallpaper, please provide the sources of all artworks used."
                   "\n\n\t\t- If source is from official media, please cite the episode, chapter, volume, etc."
                   "\n\n\t- Respect the artist and their work - do not impersonate, steal from, or infringe on the "
                   "copyright of other artists.")

    async def evaluate(self,
                       submission: Submission,
                       removal_flag: Event,
                       warning_flag: Event,
                       enabled: bool,
                       timeout_hrs: int):
        if not enabled:
            return
        deadline_utc = submission.created_utc + 3600 * timeout_hrs
        await submission.comments.replace_more(limit=None)
        while True:
            try:
                await wait_for(removal_flag.wait(), timeout=60)
            except TimeoutError:
                await submission.load()
                # Check if submission was manually moderated and cancel if yes
                removed = submission.banned_by is not None and submission.banned_by != "AutoModerator"
                deleted = submission.removed_by_category == "deleted"
                approved = submission.approved_by is not None
                if any((removed, deleted, approved)):
                    return
                comments = await submission.comments()
                for comment in comments:
                    if comment.author.name == submission.author.name:
                        return
                if deadline_utc <= time.time():
                    break
                continue
            else:
                return
        removal_flag.set()
        return self.removal_comment.format(timeout=timeout_hrs, many='s' if timeout_hrs != 1 else '') + self.description


class RateLimitAny(Rule):
    removal_comment = "\n\n- **Rate limit reached.**"
    section_template = "\n\n\t- You cannot submit more than **{freq} posts in a {intvl}-hour period.** You submitted:"
    active_template = "\n\n\t\t- [{submission_id}](https://redd.it/{submission_id}) ({dur})"
    next_template = "\n\n\t- Please wait until **{next_time} UTC** to submit again. {incl_deleted}"
    deleted_comment = "Deleted submissions will still be counted towards the rate limit."

    async def evaluate(self,
                       submission: Submission,
                       removal_flag: Event,
                       warning_flag: Event,
                       enabled: bool,
                       interval_hours: int,
                       frequency: int,
                       incl_deleted: bool = True) -> str | None:
        if not enabled:
            return
        interval_seconds = interval_hours * 3600
        async with async_database_ctx(self.mysql_auth) as db:
            await db.execute(f"SELECT s.id, s.created_utc, "
                             f"TIMESTAMPDIFF(hour,FROM_UNIXTIME(s.created_utc),FROM_UNIXTIME(l.created_utc)) AS hours_since,"
                             f"TIMESTAMPDIFF(minute,FROM_UNIXTIME(s.created_utc),FROM_UNIXTIME(l.created_utc)) AS minutes_since "
                             f"FROM submissions s, (SELECT id, author, created_utc, subreddit "
                             f"FROM submissions WHERE id=%s) l "
                             f"WHERE s.author=l.author AND s.subreddit=l.subreddit AND s.id!=l.id "
                             f"{'AND NOT s.deleted' if not incl_deleted else ''} AND NOT s.removed "
                             f"AND l.created_utc-s.created_utc<%s "
                             f"ORDER BY s.created_utc DESC",
                             (submission.id, interval_seconds))
            rows = await db.fetchall()
        if len(rows) >= frequency:
            removal_flag.set()
            active_str = [
                self.active_template.format(
                    submission_id=row["id"],
                    dur=self.format_duration(row["hours_since"], row["minutes_since"])
                ) for row in rows
            ]
            next_str = self.next_template.format(
                next_time=time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(rows[-1]['created_utc'] + interval_seconds)),
                incl_deleted=self.deleted_comment if incl_deleted else ''
            )
            return (self.removal_comment
                    + self.section_template.format(freq=frequency, intvl=interval_hours)
                    + ''.join(active_str)
                    + next_str)

    @staticmethod
    def format_duration(hours_since, minutes_since):
        if hours_since == 0 and minutes_since == 0:
            return 'just now'
        duration_minute = minutes_since % 60
        hour_str = (f'{hours_since} hours' if hours_since > 1 else f'1 hour' if hours_since == 1 else '')
        minute_str = (f', {str(duration_minute)} minutes' if duration_minute > 1 else f', 1 minute' if duration_minute == 1 else '')
        return (hour_str + minute_str + " ago").lstrip(", ")


reddit_auth = get_reddit_auth()
rabbitmq_auth = get_rabbitmq_auth(True)
mysql_auth = get_mysql_auth(True, as_root=True)
acr_app = Celery('match_app',
                 backend=f'db+mysql://root:{mysql_auth["password"]}@{mysql_auth["host"]}/celery',
                 broker=f'pyamqp://{rabbitmq_auth["login"]}:{rabbitmq_auth["password"]}@{rabbitmq_auth["host"]}//')


class RepostAny(Rule):
    removal_comment = "\n\n- **Repost detected.**"
    section_comment = "\n\n\t- Please avoid reposting images submitted in the last {n} month{pl}."
    match_str = "\n\n\t\t- [Image #{n}]({url}) matched submission [{match_submission}](https://redd.it/{match_submission}) ({dur}, [{pct:.2%} certainty]({match_url}))"

    async def evaluate(self,
                       submission: Submission,
                       removal_flag: Event,
                       warning_flag: Event,
                       enabled: bool,
                       report_only: bool,
                       similarity_pct: float,
                       threshold_months: int) -> str | None:
        if not enabled:
            return
        acr_task = acr_app.send_task('get_similarity', (submission.id, threshold_months, similarity_pct))
        while not acr_task.ready():
            try:
                await wait_for(removal_flag.wait(), timeout=30)
            except TimeoutError:
                await submission.load()
                # Check if submission was manually moderated and cancel if yes
                removed = submission.banned_by is not None and submission.banned_by != "AutoModerator"
                deleted = submission.removed_by_category == "deleted"
                approved = submission.approved_by is not None
                if any((removed, deleted, approved)):
                    acr_app.control.revoke(acr_task.id, terminate=True)
                    return
                continue
            else:
                acr_app.control.revoke(acr_task.id, terminate=True)
                return
        results = acr_task.get()
        results_formatted = await self.format_results(results, submission.created_utc)
        if len(results_formatted) > 0:
            removal_flag.set() if not report_only else warning_flag.set()
            return (self.removal_comment +
                    self.section_comment.format(n=threshold_months, pl='s' if threshold_months > 1 else '') +
                    ''.join(results_formatted))

    async def format_results(self, results: dict, created_utc):
        results_str = []
        created_dt = datetime.utcfromtimestamp(created_utc)
        async with async_database_ctx(self.mysql_auth) as db:
            for i, match in enumerate(results.items()):
                image_id, matches = match
                await db.execute('select url from submissions s join images i on s.id = i.submission_id where i.id=%s', image_id)
                image_row = await db.fetchone()
                url = image_row['url']
                for matched_id, pct in matches:
                    await db.execute('select submission_id, url, created_utc from submissions s join images i on s.id = i.submission_id where i.id=%s', matched_id)
                    match_row = await db.fetchone()
                    match_submission = match_row['submission_id']
                    if not await self.submission_alive(match_submission):
                        continue
                    match_url = match_row['url']
                    match_utc = match_row['created_utc']
                    time_since = self.get_time_since(datetime.utcfromtimestamp(match_utc), created_dt)
                    results_str.append(self.match_str.format(n=i+1, url=url, match_submission=match_submission, dur=time_since, pct=pct, match_url=match_url))
        return results_str

    @staticmethod
    def get_time_since(dt_start: datetime, dt_end: datetime):
        md, td = monthmod(dt_start, dt_end)
        if md.months > 0:
            return f"{md.months} month{'s' if md.months != 1 else ''} ago"
        if td.days > 0:
            return f"{td.days} day{'s' if td.days != 1 else ''} ago"
        if td.seconds >= 3600:
            hours = td.seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        if td.seconds >= 60:
            minutes = td.seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        return "just now"

    @staticmethod
    async def submission_alive(submission_id: str) -> bool:
        async with Reddit(**reddit_auth, timeout=30) as reddit:
            submission = await reddit.submission(submission_id)
            async with async_database_ctx(mysql_auth) as db:
                removed = submission.banned_by is not None
                deleted = submission.removed_by_category == "deleted"
                if removed or deleted:
                    await db.execute('UPDATE submissions SET removed=%s,deleted=%s WHERE id=%s', (removed, deleted, submission_id))
                    return False
        return True


class RuleBook:
    prefix_comment = ("Thank you for contributing to r/{subreddit}! "
                      "Unfortunately, your submission was removed for the following reason{many}:")
    signature_comment = ("\n\n*I am a bot, and this action was performed automatically. Please [contact the moderators "
                         "of this subreddit](https://reddit.com/message/compose/?to=/r/{subreddit}) if you have any "
                         "questions or concerns.*")

    def __init__(self, submission: Submission, settings, mysql_auth):
        self.submission = submission
        self.settings = settings
        self.removal_flag = Event()
        self.warning_flag = Event()
        self.skip_flag = Event()
        self.comments = []
        self.mysql_auth = mysql_auth
        self.log = logging.getLogger(__name__)

    async def evaluate(self):
        tasks = [create_task(self._evaluate_with_rule(self.submission, name)) for name in active_rules]
        results = await gather(*tasks)
        self.comments.extend([str(result) for result in results if result is not None])

    async def _evaluate_with_rule(self, submission: Submission, name: str):
        if (got_rule := rule_from_name(name)(self.mysql_auth)) is not None:
            return await got_rule.evaluate(**self.settings[name],
                                           submission=submission,
                                           removal_flag=self.removal_flag,
                                           warning_flag=self.warning_flag)

    async def evaluate_flair(self):
        # TODO: option to enforce image vs gallery filter (i.e. "image, gallery")
        flair_str = self.submission.link_flair_text
        if flair_str not in self.settings['flairs']:
            return
        flair_setting: str = self.settings['flairs'][flair_str]
        if flair_setting == "skip":
            self.skip_flag.set()
            return
        async with async_database_ctx(self.mysql_auth) as db:
            query_flairs = ','.join(f"'{flair_str.strip()}'" for flair_str in flair_setting.split(','))
            query = (f"SELECT fs.id, fs.orientation, fs.url "
                     f"FROM (SELECT i.id, "
                     f"IF(i.width > i.height, 'horizontal', IF(i.width < i.height, 'vertical', 'square')) "
                     f"AS orientation, i.url "
                     f"FROM submissions s JOIN images i ON s.id = i.submission_id "
                     f"WHERE s.id=%s ORDER BY i.id) fs "
                     f"WHERE fs.orientation not in ({query_flairs})")
            await db.execute(query, self.submission.id)
            rows = await db.fetchall()
        if len(rows) > 0:
            self.removal_flag.set()
            bad_image_dict = {"horizontal": [], "vertical": [], "square": []}
            for i in range(len(rows)):
                bad_image_dict[rows[i]['orientation']].append(i)
            h_section = self._format_section('horizontal', bad_image_dict, rows, flair_str)
            v_section = self._format_section('vertical', bad_image_dict, rows, flair_str)
            s_section = self._format_section('square', bad_image_dict, rows, flair_str)
            self.comments.append(h_section + v_section + s_section)

    @staticmethod
    def _format_section(orientation, bad_image_dict, bad_images_rows, flair_str):
        if len(bad_image_dict[orientation]) == 0:
            return ""
        section_str = f"\n\n- {orientation.capitalize()} images are not allowed under the **{flair_str}** flair."
        square_images_str = ', '.join(
            f"[Image #{i + 1}]({bad_images_rows[i]['url']})" for i in bad_image_dict[orientation]
        )
        deficiency_str = (f"\n\n\t- {square_images_str} "
                          f"{'are' if len(bad_image_dict[orientation]) != 1 else 'is'} {orientation}.")
        return section_str + deficiency_str

    def should_remove(self):
        return self.removal_flag.is_set()

    def should_skip(self):
        return self.skip_flag.is_set()

    def should_warn(self):
        return self.warning_flag.is_set()

    def get_removal_comment(self):
        subreddit = self.submission.subreddit.display_name
        many = "s" if len(self.comments) != 1 else ''
        return (self.prefix_comment.format(subreddit=subreddit, many=many)
                + ''.join(self.comments)
                + self.signature_comment.format(subreddit=subreddit))


active_rules: tuple[str, ...] = (
    ResolutionMismatch.__name__,
    ResolutionBad.__name__,
    AspectRatioBad.__name__,
    RateLimitAny.__name__,
    SourceCommentAny.__name__,
    RepostAny.__name__,
)


# https://stackoverflow.com/a/30042585
# https://bytes.com/topic/python/answers/702589-can-you-use-getattr-get-function-current-module#post2793206
def rule_from_name(name: str):
    if name in active_rules:
        return globals()[name]
