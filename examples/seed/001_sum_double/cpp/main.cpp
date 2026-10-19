#include <iomanip>
#include <iostream>

int main() {
    int n = 0;
    if (!(std::cin >> n)) {
        return 1;
    }

    double total = 0.0;
    for (int i = 0; i < n; ++i) {
        double x = 0.0;
        if (!(std::cin >> x)) {
            return 1;
        }
        total += x;
    }

    std::cout << std::fixed << std::setprecision(6) << std::setw(12) << total << '\n';
    return 0;
}
