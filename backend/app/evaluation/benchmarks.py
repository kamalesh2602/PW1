"""
Predefined benchmark suite for M8 Baseline Comparison and Evaluation.
Contains 10 controlled benchmark tasks (B001 to B010) reproducing specific bug categories.
"""

from app.evaluation.models import BenchmarkCase


BENCHMARKS: dict[str, BenchmarkCase] = {
    "B001": BenchmarkCase(
        bug_id="B001",
        category="ZeroDivisionError",
        title="Division by Zero in Function Call",
        language="python",
        code="""def calculate(x):
    return 10 / x

def process():
    value = 0
    return calculate(value)

process()""",
        stdin="",
        expected_error="ZeroDivisionError",
        description="A nested function performs arithmetic division where the divisor argument evaluates to zero at runtime.",
        expected_root_cause="The caller process() initializes value to 0 and passes it into calculate(), where it is used directly as the divisor in 10 / x without validation.",
        expected_behavior="process() should provide a non-zero divisor (or calculate() should handle a zero divisor safely) so that 10 / x computes a valid numeric quotient without raising ZeroDivisionError."
    ),
    "B002": BenchmarkCase(
        bug_id="B002",
        category="IndexError",
        title="Rank Index Calculation Exceeds Bounds",
        language="python",
        code="""def compute_rank_index(players, rank):
    return rank

def get_ranked_player(players, rank_idx):
    return players[rank_idx]

def evaluate_leaderboard():
    leaderboard = ["Alice", "Bob", "Charlie"]
    idx = compute_rank_index(leaderboard, 3)
    return get_ranked_player(leaderboard, idx)

evaluate_leaderboard()""",
        stdin="",
        expected_error="IndexError",
        description="1-based rank computation directly indexes a 0-based list, resulting in an out-of-range index lookup on the final rank.",
        expected_root_cause="compute_rank_index() returns the 1-based rank value (3) without converting it to a 0-based index (rank - 1), causing get_ranked_player() to access index 3 on a 3-element list with valid indices 0 to 2.",
        expected_behavior="compute_rank_index() should convert 1-based rank to 0-based index (rank - 1), allowing get_ranked_player() to access leaderboard[2] and return 'Charlie'."
    ),
    "B003": BenchmarkCase(
        bug_id="B003",
        category="KeyError",
        title="Missing Authentication Header Key",
        language="python",
        code="""def extract_header(headers, header_name):
    return headers[header_name]

def authenticate_session(request_data):
    headers = request_data.get("headers", {})
    token = extract_header(headers, "authorization")
    return f"Bearer {token}"

def handle_incoming_request():
    request = {
        "endpoint": "/api/v1/resource",
        "headers": {
            "content-type": "application/json",
            "auth_token": "secret_abc123"
        }
    }
    return authenticate_session(request)

handle_incoming_request()""",
        stdin="",
        expected_error="KeyError",
        description="Authentication handler attempts direct dictionary access for 'authorization' key when client header was supplied as 'auth_token'.",
        expected_root_cause="authenticate_session() attempts to retrieve key 'authorization' from the headers dictionary, but the client request payload was provided with key 'auth_token', causing extract_header() to raise KeyError.",
        expected_behavior="The header lookup should access 'auth_token' (or handle missing headers gracefully), returning 'Bearer secret_abc123'."
    ),
    "B004": BenchmarkCase(
        bug_id="B004",
        category="TypeError",
        title="String and Float Arithmetic Mismatch Across Calls",
        language="python",
        code="""def parse_configuration(raw_config):
    return {
        "service": raw_config.get("name"),
        "timeout": raw_config.get("timeout_sec", "30")
    }

def calculate_deadline(base_time, timeout):
    return base_time + timeout

def schedule_job():
    config = parse_configuration({"name": "worker", "timeout_sec": "45"})
    start_time = 100.0
    deadline = calculate_deadline(start_time, config["timeout"])
    return deadline

schedule_job()""",
        stdin="",
        expected_error="TypeError",
        description="Configuration parser propagates timeout as a string rather than a numeric value, causing a TypeError when added to a float timestamp.",
        expected_root_cause="parse_configuration() keeps 'timeout_sec' as string '45' instead of casting it to float or int, causing calculate_deadline() to attempt arithmetic addition between float 100.0 and string '45'.",
        expected_behavior="The timeout value should be cast to a numeric type (float or int), allowing calculate_deadline() to perform addition and return 145.0."
    ),
    "B005": BenchmarkCase(
        bug_id="B005",
        category="ValueError",
        title="Invalid Literal in Transaction Segment Parsing",
        language="python",
        code="""def extract_numeric_code(code_str):
    return int(code_str)

def parse_transaction(raw_tx):
    parts = raw_tx.split(":")
    tag = parts[0]
    tx_code = parts[1]
    return extract_numeric_code(tx_code)

def execute_transaction():
    tx_data = "TX:TRANSFER_99:250"
    return parse_transaction(tx_data)

execute_transaction()""",
        stdin="",
        expected_error="ValueError",
        description="Transaction parser indexes an alphanumeric identifier segment instead of the numeric amount segment when converting to integer.",
        expected_root_cause="parse_transaction() extracts parts[1] ('TRANSFER_99', the transaction label) instead of parts[2] ('250', the numeric amount) and passes it to extract_numeric_code(), where int() fails on non-digit characters.",
        expected_behavior="parse_transaction() should extract the numeric amount segment (parts[2]) so extract_numeric_code() successfully returns integer 250."
    ),
    "B006": BenchmarkCase(
        bug_id="B006",
        category="Logic error",
        title="Accidental Reset in Discount Accumulator Loop",
        language="python",
        code="""def calculate_total_discount(prices, discount_rate):
    total_discount = 0.0
    for price in prices:
        discount = price * discount_rate
        total_discount = discount
    return total_discount

def run_cart():
    items = [100.0, 200.0, 50.0]
    rate = 0.10
    result = calculate_total_discount(items, rate)
    print(f"Total discount: {result}")
    return result

run_cart()""",
        stdin="",
        expected_error="LogicError (Incorrect Output)",
        description="Loop execution reassigns the accumulator variable instead of adding to it, causing only the last iteration's discount to be returned.",
        expected_root_cause="The accumulator total_discount is overwritten inside the loop (total_discount = discount) rather than accumulated (total_discount += discount), causing the function to discard previous item discounts and return only the final iteration's value (5.0 instead of 35.0).",
        expected_behavior="The loop should accumulate discounts across all items (total_discount += discount), producing a total discount of 35.0 across the three items [100.0, 200.0, 50.0] at a 10% rate."
    ),
    "B007": BenchmarkCase(
        bug_id="B007",
        category="State/mutation bug",
        title="Mutable Default Argument Permission Leak",
        language="python",
        code="""def create_user_session(user_id, permissions=[]):
    permissions.append("read")
    return {"user_id": user_id, "permissions": permissions}

def grant_admin(session):
    session["permissions"].append("admin")
    return session

def run_security_pipeline():
    user1 = create_user_session("alice")
    grant_admin(user1)
    user2 = create_user_session("bob")
    assert "admin" not in user2["permissions"], f"Security violation: {user2['user_id']} leaked admin permission"
    return user2

run_security_pipeline()""",
        stdin="",
        expected_error="AssertionError",
        description="A function uses a mutable list as a default parameter, causing state modifications from earlier calls to contaminate subsequent user sessions.",
        expected_root_cause="create_user_session() defines a mutable default argument (permissions=[]), which is evaluated once at definition time and shared across calls. When alice is granted 'admin', the shared list is mutated, causing bob's new session to inherit alice's admin permission and trigger an AssertionError.",
        expected_behavior="create_user_session() should use permissions=None and initialize a new list inside the function (permissions = [] if permissions is None else permissions), ensuring user sessions do not share mutable state and bob is not granted admin."
    ),
    "B008": BenchmarkCase(
        bug_id="B008",
        category="Class/OOP bug",
        title="Incompatible None State in Order Cancellation",
        language="python",
        code="""class OrderManager:
    def __init__(self, order_id: str):
        self.order_id = order_id
        self.status = "pending"
        self.items = {}

    def add_item(self, item_name: str, quantity: int):
        self.items[item_name] = quantity

    def cancel_order(self):
        self.status = "cancelled"
        self.items = None

    def get_total_items(self):
        return sum(self.items.values())

def process_cancellation():
    manager = OrderManager("ORD-501")
    manager.add_item("keyboard", 1)
    manager.add_item("mouse", 2)
    manager.cancel_order()
    return manager.get_total_items()

process_cancellation()""",
        stdin="",
        expected_error="AttributeError",
        description="An order management class resets an instance attribute dictionary to None upon cancellation, breaking subsequent method calls expecting a collection.",
        expected_root_cause="cancel_order() resets self.items to None instead of clearing the dictionary (self.items.clear() or self.items = {}), causing get_total_items() to raise an AttributeError when attempting to call .values() on NoneType.",
        expected_behavior="cancel_order() should reset self.items to an empty dictionary or clear it, so get_total_items() safely computes a sum of 0 items without an AttributeError."
    ),
    "B009": BenchmarkCase(
        bug_id="B009",
        category="Inheritance/polymorphism bug",
        title="Case-Sensitive Lookup in Overridden Polymorphic Method",
        language="python",
        code="""class BaseAccount:
    def __init__(self, account_holder: str, initial_balance: float):
        self.account_holder = account_holder
        self.balance = initial_balance

    def calculate_interest(self) -> float:
        return self.balance * 0.01

    def apply_annual_charge(self) -> float:
        interest = self.calculate_interest()
        self.balance += interest
        return self.balance

class PremiumAccount(BaseAccount):
    def __init__(self, account_holder: str, initial_balance: float, tier: str):
        super().__init__(account_holder, initial_balance)
        self.tier = tier

    def calculate_interest(self) -> float:
        tier_multipliers = {"gold": 0.05, "platinum": 0.08}
        multiplier = tier_multipliers[self.tier]
        return self.balance * multiplier

def run_accounting():
    account = PremiumAccount("Dr. Smith", 10000.0, "Gold")
    return account.apply_annual_charge()

run_accounting()""",
        stdin="",
        expected_error="KeyError",
        description="A derived class overrides a base calculation method called polymorphically by a base method, but performs a case-sensitive dictionary lookup against unnormalized instance state.",
        expected_root_cause="PremiumAccount.calculate_interest() overrides BaseAccount.calculate_interest() and attempts a direct dictionary lookup tier_multipliers[self.tier] without normalizing the string, raising KeyError: 'Gold' because the dictionary keys are lowercase ('gold', 'platinum').",
        expected_behavior="PremiumAccount.calculate_interest() should normalize self.tier using .lower(), allowing tier_multipliers['gold'] to resolve to 0.05 and returning an updated balance of 10500.0."
    ),
    "B010": BenchmarkCase(
        bug_id="B010",
        category="Multi-function / deeper call-chain bug",
        title="Multi-Frame Buffer Offset Boundary Overshoot",
        language="python",
        code="""def read_chunk_byte(buffer, offset):
    return buffer[offset]

def unpack_header_field(data_bytes, start_pos, length):
    end_pos = start_pos + length
    return read_chunk_byte(data_bytes, end_pos)

def parse_packet_metadata(raw_packet):
    header = raw_packet.get("header_bytes", b"")
    field_length = 8
    return unpack_header_field(header, 0, field_length)

def route_network_packet():
    packet = {
        "packet_id": 1001,
        "header_bytes": b"PKT_HEAD"
    }
    return parse_packet_metadata(packet)

route_network_packet()""",
        stdin="",
        expected_error="IndexError",
        description="A call chain of 4 functions passes an off-by-one computed boundary down to a low-level buffer reader, triggering an out-of-bounds index error several frames deep.",
        expected_root_cause="unpack_header_field() computes end_pos = start_pos + length (8) and passes it as a single-byte index to read_chunk_byte(), which attempts to access buffer[8] on an 8-byte buffer whose valid 0-based indices are 0 to 7.",
        expected_behavior="unpack_header_field() should pass start_pos (or slice data_bytes[start_pos:end_pos]) rather than end_pos to read_chunk_byte(), avoiding the out-of-range IndexError and returning the packet header."
    ),
}

PYTHON_BENCHMARKS = BENCHMARKS

JAVA_BENCHMARKS: dict[str, BenchmarkCase] = {
    "B001": BenchmarkCase(
        bug_id="B001",
        category="ArithmeticException",
        title="Division by Zero in Function Call",
        language="java",
        code="""public class Main {
    public static int calculate(int x) {
        return 10 / x;
    }

    public static int process() {
        int value = 0;
        return calculate(value);
    }

    public static void main(String[] args) {
        process();
    }
}""",
        stdin="",
        expected_error="ArithmeticException",
        description="A nested method performs arithmetic division where the divisor argument evaluates to zero at runtime.",
        expected_root_cause="The caller process() initializes value to 0 and passes it into calculate(), where it is used directly as the divisor in 10 / x without validation, throwing an ArithmeticException.",
        expected_behavior="process() should provide a non-zero divisor (or calculate() should handle a zero divisor safely) so that 10 / x computes a valid numeric quotient without raising ArithmeticException."
    ),
    "B002": BenchmarkCase(
        bug_id="B002",
        category="ArrayIndexOutOfBoundsException",
        title="Rank Index Calculation Exceeds Bounds",
        language="java",
        code="""public class Main {
    public static int computeRankIndex(String[] players, int rank) {
        return rank;
    }

    public static String getRankedPlayer(String[] players, int rankIdx) {
        return players[rankIdx];
    }

    public static String evaluateLeaderboard() {
        String[] leaderboard = {"Alice", "Bob", "Charlie"};
        int idx = computeRankIndex(leaderboard, 3);
        return getRankedPlayer(leaderboard, idx);
    }

    public static void main(String[] args) {
        System.out.println(evaluateLeaderboard());
    }
}""",
        stdin="",
        expected_error="ArrayIndexOutOfBoundsException",
        description="1-based rank computation directly indexes a 0-based array, resulting in an out-of-range index lookup on the final rank.",
        expected_root_cause="computeRankIndex() returns the 1-based rank value (3) without converting it to a 0-based index (rank - 1), causing getRankedPlayer() to access index 3 on a 3-element array with valid indices 0 to 2.",
        expected_behavior="computeRankIndex() should convert 1-based rank to 0-based index (rank - 1), allowing getRankedPlayer() to access leaderboard[2] and return 'Charlie'."
    ),
    "B003": BenchmarkCase(
        bug_id="B003",
        category="NoSuchElementException",
        title="Missing Authentication Header Key",
        language="java",
        code="""import java.util.HashMap;
import java.util.Map;
import java.util.NoSuchElementException;

public class Main {
    public static String extractHeader(Map<String, String> headers, String headerName) {
        if (!headers.containsKey(headerName)) {
            throw new NoSuchElementException("Header not found: " + headerName);
        }
        return headers.get(headerName);
    }

    public static String authenticateSession(Map<String, Object> requestData) {
        @SuppressWarnings("unchecked")
        Map<String, String> headers = (Map<String, String>) requestData.getOrDefault("headers", new HashMap<String, String>());
        String token = extractHeader(headers, "authorization");
        return "Bearer " + token;
    }

    public static String handleIncomingRequest() {
        Map<String, Object> request = new HashMap<>();
        request.put("endpoint", "/api/v1/resource");
        Map<String, String> headers = new HashMap<>();
        headers.put("content-type", "application/json");
        headers.put("auth_token", "secret_abc123");
        request.put("headers", headers);
        return authenticateSession(request);
    }

    public static void main(String[] args) {
        System.out.println(handleIncomingRequest());
    }
}""",
        stdin="",
        expected_error="NoSuchElementException",
        description="Authentication handler attempts direct map access for 'authorization' key when client header was supplied as 'auth_token'.",
        expected_root_cause="authenticateSession() attempts to retrieve key 'authorization' from the headers map, but the client request payload was provided with key 'auth_token', causing extractHeader() to throw NoSuchElementException.",
        expected_behavior="The header lookup should access 'auth_token' (or handle missing headers gracefully), returning 'Bearer secret_abc123'."
    ),
    "B004": BenchmarkCase(
        bug_id="B004",
        category="ClassCastException",
        title="String and Double Type Mismatch Across Calls",
        language="java",
        code="""import java.util.HashMap;
import java.util.Map;

public class Main {
    public static Map<String, Object> parseConfiguration(Map<String, String> rawConfig) {
        Map<String, Object> config = new HashMap<>();
        config.put("service", rawConfig.get("name"));
        config.put("timeout", rawConfig.getOrDefault("timeout_sec", "30"));
        return config;
    }

    public static double calculateDeadline(double baseTime, Object timeout) {
        Double timeoutVal = (Double) timeout;
        return baseTime + timeoutVal;
    }

    public static double scheduleJob() {
        Map<String, String> raw = new HashMap<>();
        raw.put("name", "worker");
        raw.put("timeout_sec", "45");
        Map<String, Object> config = parseConfiguration(raw);
        double startTime = 100.0;
        return calculateDeadline(startTime, config.get("timeout"));
    }

    public static void main(String[] args) {
        System.out.println(scheduleJob());
    }
}""",
        stdin="",
        expected_error="ClassCastException",
        description="Configuration parser propagates timeout as a String rather than a numeric Double, causing a ClassCastException when cast for arithmetic.",
        expected_root_cause="parseConfiguration() keeps 'timeout_sec' as string '45' instead of parsing it to a Double, causing calculateDeadline() to attempt casting a String to Double.",
        expected_behavior="The timeout value should be parsed to a numeric Double (Double.parseDouble), allowing calculateDeadline() to perform addition and return 145.0."
    ),
    "B005": BenchmarkCase(
        bug_id="B005",
        category="NumberFormatException",
        title="Invalid Number Format in Transaction Segment Parsing",
        language="java",
        code="""public class Main {
    public static int extractNumericCode(String codeStr) {
        return Integer.parseInt(codeStr);
    }

    public static int parseTransaction(String rawTx) {
        String[] parts = rawTx.split(":");
        String tag = parts[0];
        String txCode = parts[1];
        return extractNumericCode(txCode);
    }

    public static int executeTransaction() {
        String txData = "TX:TRANSFER_99:250";
        return parseTransaction(txData);
    }

    public static void main(String[] args) {
        System.out.println(executeTransaction());
    }
}""",
        stdin="",
        expected_error="NumberFormatException",
        description="Transaction parser indexes an alphanumeric identifier segment instead of the numeric amount segment when converting to integer.",
        expected_root_cause="parseTransaction() extracts parts[1] ('TRANSFER_99', the transaction label) instead of parts[2] ('250', the numeric amount) and passes it to extractNumericCode(), where Integer.parseInt() fails with NumberFormatException.",
        expected_behavior="parseTransaction() should extract the numeric amount segment (parts[2]) so extractNumericCode() successfully returns integer 250."
    ),
    "B006": BenchmarkCase(
        bug_id="B006",
        category="Logic error",
        title="Accidental Reset in Discount Accumulator Loop",
        language="java",
        code="""public class Main {
    public static double calculateTotalDiscount(double[] prices, double discountRate) {
        double totalDiscount = 0.0;
        for (double price : prices) {
            double discount = price * discountRate;
            totalDiscount = discount;
        }
        return totalDiscount;
    }

    public static double runCart() {
        double[] items = {100.0, 200.0, 50.0};
        double rate = 0.10;
        double result = calculateTotalDiscount(items, rate);
        System.out.println("Total discount: " + result);
        return result;
    }

    public static void main(String[] args) {
        double res = runCart();
        if (Math.abs(res - 35.0) > 1e-4) {
            throw new IllegalStateException("Incorrect total discount: " + res);
        }
    }
}""",
        stdin="",
        expected_error="LogicError / IllegalStateException",
        description="Loop execution reassigns the accumulator variable instead of adding to it, causing only the last iteration's discount to be returned.",
        expected_root_cause="The accumulator totalDiscount is overwritten inside the loop (totalDiscount = discount) rather than accumulated (totalDiscount += discount), causing previous item discounts to be discarded and returning 5.0 instead of 35.0.",
        expected_behavior="The loop should accumulate discounts across all items (totalDiscount += discount), producing a total discount of 35.0 across the three items [100.0, 200.0, 50.0] at a 10% rate."
    ),
    "B007": BenchmarkCase(
        bug_id="B007",
        category="State/mutation bug",
        title="Shared Mutable Default Permission Leak",
        language="java",
        code="""import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class Main {
    private static final List<String> DEFAULT_PERMISSIONS = new ArrayList<>();

    public static Map<String, Object> createUserSession(String userId, List<String> permissions) {
        if (permissions == null) {
            permissions = DEFAULT_PERMISSIONS;
        }
        permissions.add("read");
        Map<String, Object> session = new HashMap<>();
        session.put("user_id", userId);
        session.put("permissions", permissions);
        return session;
    }

    public static Map<String, Object> grantAdmin(Map<String, Object> session) {
        @SuppressWarnings("unchecked")
        List<String> perms = (List<String>) session.get("permissions");
        perms.add("admin");
        return session;
    }

    public static Map<String, Object> runSecurityPipeline() {
        Map<String, Object> user1 = createUserSession("alice", null);
        grantAdmin(user1);
        Map<String, Object> user2 = createUserSession("bob", null);
        @SuppressWarnings("unchecked")
        List<String> perms2 = (List<String>) user2.get("permissions");
        if (perms2.contains("admin")) {
            throw new AssertionError("Security violation: " + user2.get("user_id") + " leaked admin permission");
        }
        return user2;
    }

    public static void main(String[] args) {
        runSecurityPipeline();
    }
}""",
        stdin="",
        expected_error="AssertionError",
        description="A method uses a shared static list as a default parameter without defensive copying, causing state mutations from earlier user sessions to contaminate subsequent user sessions.",
        expected_root_cause="createUserSession() reuses a shared mutable list (DEFAULT_PERMISSIONS) across calls when permissions is null. When alice is granted 'admin', the shared list is mutated, causing bob's new session to inherit alice's admin permission and throw AssertionError.",
        expected_behavior="createUserSession() should create a new ArrayList<>() for default permissions (new ArrayList<>()), ensuring user sessions do not share mutable state and bob is not granted admin."
    ),
    "B008": BenchmarkCase(
        bug_id="B008",
        category="NullPointerException",
        title="Incompatible Null State in Order Cancellation",
        language="java",
        code="""import java.util.HashMap;
import java.util.Map;

class OrderManager {
    public String orderId;
    public String status;
    public Map<String, Integer> items;

    public OrderManager(String orderId) {
        this.orderId = orderId;
        this.status = "pending";
        this.items = new HashMap<>();
    }

    public void addItem(String itemName, int quantity) {
        this.items.put(itemName, quantity);
    }

    public void cancelOrder() {
        this.status = "cancelled";
        this.items = null;
    }

    public int getTotalItems() {
        int total = 0;
        for (int q : this.items.values()) {
            total += q;
        }
        return total;
    }
}

public class Main {
    public static int processCancellation() {
        OrderManager manager = new OrderManager("ORD-501");
        manager.addItem("keyboard", 1);
        manager.addItem("mouse", 2);
        manager.cancelOrder();
        return manager.getTotalItems();
    }

    public static void main(String[] args) {
        System.out.println(processCancellation());
    }
}""",
        stdin="",
        expected_error="NullPointerException",
        description="An order management class resets an instance attribute map to null upon cancellation, breaking subsequent method calls expecting a collection.",
        expected_root_cause="cancelOrder() resets this.items to null instead of clearing the map (this.items.clear() or this.items = new HashMap<>()), causing getTotalItems() to throw a NullPointerException when attempting to iterate this.items.values().",
        expected_behavior="cancelOrder() should reset this.items to an empty map or clear it, so getTotalItems() safely computes a sum of 0 items without a NullPointerException."
    ),
    "B009": BenchmarkCase(
        bug_id="B009",
        category="NullPointerException",
        title="Case-Sensitive Lookup in Overridden Polymorphic Method",
        language="java",
        code="""import java.util.HashMap;
import java.util.Map;

class BaseAccount {
    public String accountHolder;
    public double balance;

    public BaseAccount(String accountHolder, double initialBalance) {
        this.accountHolder = accountHolder;
        this.balance = initialBalance;
    }

    public double calculateInterest() {
        return this.balance * 0.01;
    }

    public double applyAnnualCharge() {
        double interest = this.calculateInterest();
        this.balance += interest;
        return this.balance;
    }
}

class PremiumAccount extends BaseAccount {
    public String tier;

    public PremiumAccount(String accountHolder, double initialBalance, String tier) {
        super(accountHolder, initialBalance);
        this.tier = tier;
    }

    @Override
    public double calculateInterest() {
        Map<String, Double> tierMultipliers = new HashMap<>();
        tierMultipliers.put("gold", 0.05);
        tierMultipliers.put("platinum", 0.08);
        Double multiplier = tierMultipliers.get(this.tier);
        return this.balance * multiplier;
    }
}

public class Main {
    public static double runAccounting() {
        PremiumAccount account = new PremiumAccount("Dr. Smith", 10000.0, "Gold");
        return account.applyAnnualCharge();
    }

    public static void main(String[] args) {
        System.out.println(runAccounting());
    }
}""",
        stdin="",
        expected_error="NullPointerException",
        description="A derived class overrides a base calculation method called polymorphically by a base method, but performs a case-sensitive map lookup against unnormalized instance state.",
        expected_root_cause="PremiumAccount.calculateInterest() overrides BaseAccount.calculateInterest() and attempts tierMultipliers.get(this.tier) without normalizing the string, returning null for 'Gold' and throwing NullPointerException upon unboxing.",
        expected_behavior="PremiumAccount.calculateInterest() should normalize this.tier using .toLowerCase(), allowing tierMultipliers.get('gold') to resolve to 0.05 and returning an updated balance of 10500.0."
    ),
    "B010": BenchmarkCase(
        bug_id="B010",
        category="ArrayIndexOutOfBoundsException",
        title="Multi-Frame Buffer Offset Boundary Overshoot",
        language="java",
        code="""import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;

public class Main {
    public static byte readChunkByte(byte[] buffer, int offset) {
        return buffer[offset];
    }

    public static byte unpackHeaderField(byte[] dataBytes, int startPos, int length) {
        int endPos = startPos + length;
        return readChunkByte(dataBytes, endPos);
    }

    public static byte parsePacketMetadata(Map<String, Object> rawPacket) {
        byte[] header = (byte[]) rawPacket.getOrDefault("header_bytes", new byte[0]);
        int fieldLength = 8;
        return unpackHeaderField(header, 0, fieldLength);
    }

    public static byte routeNetworkPacket() {
        Map<String, Object> packet = new HashMap<>();
        packet.put("packet_id", 1001);
        packet.put("header_bytes", "PKT_HEAD".getBytes(StandardCharsets.UTF_8));
        return parsePacketMetadata(packet);
    }

    public static void main(String[] args) {
        System.out.println(routeNetworkPacket());
    }
}""",
        stdin="",
        expected_error="ArrayIndexOutOfBoundsException",
        description="A call chain of 4 methods passes an off-by-one computed boundary down to a low-level buffer reader, triggering an out-of-bounds array access several frames deep.",
        expected_root_cause="unpackHeaderField() computes endPos = startPos + length (8) and passes it as a single-byte index to readChunkByte(), which attempts to access buffer[8] on an 8-byte array whose valid 0-based indices are 0 to 7.",
        expected_behavior="unpackHeaderField() should pass startPos (or read within bounds 0 to length - 1) rather than endPos to readChunkByte(), avoiding ArrayIndexOutOfBoundsException and returning the packet byte."
    ),
}


def get_all_benchmarks(language: str = "python") -> list[BenchmarkCase]:
    """Return all predefined benchmark cases in order for the specified language."""
    if language and language.strip().lower() == "java":
        return list(JAVA_BENCHMARKS.values())
    return list(PYTHON_BENCHMARKS.values())


def get_benchmark(bug_id: str, language: str = "python") -> BenchmarkCase | None:
    """Retrieve benchmark case by ID and language (case-insensitive)."""
    clean_id = bug_id.strip().upper()
    if language and language.strip().lower() == "java":
        return JAVA_BENCHMARKS.get(clean_id)
    return PYTHON_BENCHMARKS.get(clean_id)

