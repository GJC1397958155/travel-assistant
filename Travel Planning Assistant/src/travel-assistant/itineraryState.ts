import { StructuredItinerary } from './types';

const PLANNING_KEYWORDS = [
  '行程',
  '旅行',
  '旅游',
  '路线',
  '攻略',
  '规划',
  '安排',
  '计划',
  '自由行',
  '度假',
];

const CHANGE_KEYWORDS = [
  '改',
  '换',
  '重新',
  '调整',
  '优化',
  '增加',
  '减少',
  '删掉',
  '不要',
  '避开',
  '想去',
  '想玩',
  '适合',
  '轻松一点',
  '紧凑一点',
];

const DETAIL_PATTERNS = [
  /\d+\s*天/,
  /第[一二三四五六七八九十0-9]+\s*天/,
  /\d+\s*晚/,
  /\d+\s*(元|块|预算)/,
  /\d{4}-\d{1,2}-\d{1,2}/,
  /\d{1,2}月\d{1,2}(日|号)?/,
  /(今天|明天|后天|这周末|下周末|下个月)/,
  /(亲子|情侣|老人|爸妈|朋友|闺蜜|一家|独自|2大1小|2大2小)/,
  /(上午|下午|晚上)/,
];

const NEW_PLAN_PATTERNS = [
  /新的?(旅行|旅游|行程|计划|规划)/,
  /重新(做|规划|安排|生成)/,
  /换个?(地方|城市|目的地)/,
  /改去/,
  /另外一?个?(旅行|旅游|行程|计划)/,
];

function normalizeMessage(text: string): string {
  return text.replace(/\s+/g, '').trim();
}

export function shouldShowProcessingItinerary(
  messageText: string,
  currentItinerary?: StructuredItinerary,
): boolean {
  if (!currentItinerary || currentItinerary.status === 'processing') {
    return false;
  }

  const text = normalizeMessage(messageText);
  if (!text) {
    return false;
  }

  if (NEW_PLAN_PATTERNS.some((pattern) => pattern.test(text))) {
    return true;
  }

  const hasPlanningKeyword = PLANNING_KEYWORDS.some((keyword) => text.includes(keyword));
  const hasChangeKeyword = CHANGE_KEYWORDS.some((keyword) => text.includes(keyword));
  const hasDetailSignal = DETAIL_PATTERNS.some((pattern) => pattern.test(text));
  const mentionsCurrentDestination =
    !!currentItinerary.destination && text.includes(normalizeMessage(currentItinerary.destination));

  return (
    (hasPlanningKeyword && (hasChangeKeyword || hasDetailSignal)) ||
    (hasChangeKeyword && (hasDetailSignal || mentionsCurrentDestination))
  );
}

export function createProcessingItinerary(): StructuredItinerary {
  return {
    status: 'processing',
  };
}
