/*
 * One hw-testing-rack's Wi-Fi in ns-3 (docs/wifi-capacity-ns3.md).
 *
 * The bay nodes (ESP32-S3, 802.11n 1x1 HT20) and the power hub are stations of one AP, 1-3 m away,
 * on channel 6.  A wired PC behind the AP is the lab server: it flashes over USB/IP, reads the
 * consoles, watches the cameras, polls and scrapes the nodes.  One run is one point of the sweep;
 * it prints one CSV line (--header prints the column names).
 *
 *   ./ns3 run "rack-wifi --scenario=ci --active=8 --txPower=11 --apDist=2 --seed=1"
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "ns3/applications-module.h"
#include "ns3/core-module.h"
#include "ns3/internet-apps-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/network-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/propagation-module.h"
#include "ns3/wifi-module.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <iostream>
#include <map>
#include <vector>

using namespace ns3;

namespace
{

Time g_start; // measurement window
Time g_stop;

bool
InWindow()
{
    return Simulator::Now() >= g_start && Simulator::Now() < g_stop;
}

/* TCP segments and retransmissions of the rack's own flows (both ends instrumented) */
uint64_t g_tcpSegs = 0;
uint64_t g_tcpRetx = 0;

void
CountTx(Ptr<const Packet> p, const TcpHeader&, Ptr<const TcpSocketBase>)
{
    if (p->GetSize() > 0 && InWindow())
    {
        g_tcpSegs++;
    }
}

void
CountRetx(Ptr<const Packet>, const TcpHeader&, const Address&, const Address&,
          Ptr<const TcpSocketBase>)
{
    if (InWindow())
    {
        g_tcpRetx++;
    }
}

void
Instrument(Ptr<Socket> s, uint32_t sndBuf, uint32_t rcvBuf)
{
    s->SetAttribute("SndBufSize", UintegerValue(sndBuf));
    s->SetAttribute("RcvBufSize", UintegerValue(rcvBuf));
    s->TraceConnectWithoutContext("Tx", MakeCallback(&CountTx));
    s->TraceConnectWithoutContext("Retransmission", MakeCallback(&CountRetx));
}

double
Percentile(std::vector<double> v, double q)
{
    if (v.empty())
    {
        return NAN;
    }
    std::sort(v.begin(), v.end());
    const double pos = q * (v.size() - 1);
    const size_t i = static_cast<size_t>(pos);
    const double f = pos - i;
    return i + 1 < v.size() ? v[i] * (1 - f) + v[i + 1] * f : v[i];
}

/*
 * A TCP stream fed at a fixed rate: USB/IP (4 KB URBs at the rate the node's USB side can feed),
 * a console, or a camera (one MJPEG frame per period, skipped while the previous one is still
 * queued).  The source never runs more than maxBacklog bytes ahead of the socket.
 */
class StreamSender : public Application
{
  public:
    static TypeId GetTypeId()
    {
        static TypeId tid = TypeId("RackStreamSender").SetParent<Application>();
        return tid;
    }

    void Setup(Address peer, uint32_t chunk, Time period, uint32_t frameMin, uint32_t frameMax,
               uint32_t maxBacklog, uint32_t sndBuf, uint32_t rcvBuf)
    {
        m_peer = peer;
        m_chunk = chunk;
        m_period = period;
        m_frameMin = frameMin;
        m_frameMax = frameMax;
        m_maxBacklog = maxBacklog;
        m_sndBuf = sndBuf;
        m_rcvBuf = rcvBuf;
        m_rng = CreateObject<UniformRandomVariable>();
    }

    uint64_t offered = 0; // bytes generated in the window
    uint64_t framesIn = 0;
    uint64_t framesSkipped = 0;

  private:
    void StartApplication() override
    {
        m_sock = Socket::CreateSocket(GetNode(), TcpSocketFactory::GetTypeId());
        Instrument(m_sock, m_sndBuf, m_rcvBuf);
        m_sock->Bind();
        m_sock->SetConnectCallback(MakeCallback(&StreamSender::Connected, this),
                                   MakeNullCallback<void, Ptr<Socket>>());
        m_sock->SetSendCallback(MakeCallback(&StreamSender::Space, this));
        m_sock->Connect(m_peer);
    }

    void StopApplication() override
    {
        m_tick.Cancel();
        if (m_sock)
        {
            m_sock->Close();
        }
    }

    void Connected(Ptr<Socket>)
    {
        /* a random phase, so that the streams do not start in lockstep */
        m_tick = Simulator::Schedule(Seconds(m_rng->GetValue(0, m_period.GetSeconds())),
                                     &StreamSender::Tick, this);
    }

    void Tick()
    {
        if (m_frameMax > 0)
        {
            const uint32_t frame = m_rng->GetInteger(m_frameMin, m_frameMax);
            if (m_backlog == 0)
            {
                m_backlog += frame;
                if (InWindow())
                {
                    offered += frame;
                    framesIn++;
                }
            }
            else if (InWindow())
            {
                framesSkipped++;
            }
        }
        else if (m_backlog + m_chunk <= m_maxBacklog)
        {
            m_backlog += m_chunk;
            if (InWindow())
            {
                offered += m_chunk;
            }
        }
        Push();
        m_tick = Simulator::Schedule(m_period, &StreamSender::Tick, this);
    }

    void Push()
    {
        while (m_backlog > 0)
        {
            const uint32_t avail = m_sock->GetTxAvailable();
            if (avail == 0)
            {
                break;
            }
            const uint32_t n = std::min({m_backlog, avail, 8192U});
            const int sent = m_sock->Send(Create<Packet>(n));
            if (sent <= 0)
            {
                break;
            }
            m_backlog -= sent;
        }
    }

    void Space(Ptr<Socket>, uint32_t)
    {
        Push();
    }

    Ptr<Socket> m_sock;
    Address m_peer;
    uint32_t m_chunk = 0;
    Time m_period;
    uint32_t m_frameMin = 0;
    uint32_t m_frameMax = 0;
    uint32_t m_maxBacklog = 0;
    uint32_t m_sndBuf = 0;
    uint32_t m_rcvBuf = 0;
    uint32_t m_backlog = 0;
    EventId m_tick;
    Ptr<UniformRandomVariable> m_rng;
};

/* The receiving end of StreamSender: counts bytes, in the window */
class CountingSink : public Application
{
  public:
    static TypeId GetTypeId()
    {
        static TypeId tid = TypeId("RackCountingSink").SetParent<Application>();
        return tid;
    }

    void Setup(uint16_t port, uint32_t sndBuf, uint32_t rcvBuf)
    {
        m_port = port;
        m_sndBuf = sndBuf;
        m_rcvBuf = rcvBuf;
    }

    uint64_t received = 0;
    Time firstRx = Seconds(-1);

  private:
    void StartApplication() override
    {
        m_sock = Socket::CreateSocket(GetNode(), TcpSocketFactory::GetTypeId());
        Instrument(m_sock, m_sndBuf, m_rcvBuf);
        m_sock->Bind(InetSocketAddress(Ipv4Address::GetAny(), m_port));
        m_sock->Listen();
        m_sock->SetAcceptCallback(MakeNullCallback<bool, Ptr<Socket>, const Address&>(),
                                  MakeCallback(&CountingSink::Accept, this));
    }

    void Accept(Ptr<Socket> s, const Address&)
    {
        s->SetRecvCallback(MakeCallback(&CountingSink::Recv, this));
    }

    void Recv(Ptr<Socket> s)
    {
        Ptr<Packet> p;
        while ((p = s->Recv()))
        {
            if (firstRx.IsNegative())
            {
                firstRx = Simulator::Now();
            }
            if (InWindow())
            {
                received += p->GetSize();
            }
        }
    }

    Ptr<Socket> m_sock;
    uint16_t m_port = 0;
    uint32_t m_sndBuf = 0;
    uint32_t m_rcvBuf = 0;
};

/* The node's HTTP server: answers respSize bytes once reqSize bytes came in, then closes */
class HttpServer : public Application
{
  public:
    static TypeId GetTypeId()
    {
        static TypeId tid = TypeId("RackHttpServer").SetParent<Application>();
        return tid;
    }

    void Setup(uint16_t port, uint32_t req, uint32_t resp, uint32_t sndBuf, uint32_t rcvBuf)
    {
        m_port = port;
        m_req = req;
        m_resp = resp;
        m_sndBuf = sndBuf;
        m_rcvBuf = rcvBuf;
    }

  private:
    void StartApplication() override
    {
        m_sock = Socket::CreateSocket(GetNode(), TcpSocketFactory::GetTypeId());
        Instrument(m_sock, m_sndBuf, m_rcvBuf);
        m_sock->Bind(InetSocketAddress(Ipv4Address::GetAny(), m_port));
        m_sock->Listen();
        m_sock->SetAcceptCallback(MakeNullCallback<bool, Ptr<Socket>, const Address&>(),
                                  MakeCallback(&HttpServer::Accept, this));
    }

    void Accept(Ptr<Socket> s, const Address&)
    {
        m_rx[s] = 0;
        s->SetRecvCallback(MakeCallback(&HttpServer::Recv, this));
    }

    void Recv(Ptr<Socket> s)
    {
        Ptr<Packet> p;
        while ((p = s->Recv()))
        {
            m_rx[s] += p->GetSize();
        }
        auto it = m_rx.find(s);
        if (it != m_rx.end() && it->second >= m_req)
        {
            m_rx.erase(it);
            s->Send(Create<Packet>(m_resp));
            s->Close();
        }
    }

    Ptr<Socket> m_sock;
    std::map<Ptr<Socket>, uint32_t> m_rx;
    uint16_t m_port = 0;
    uint32_t m_req = 0;
    uint32_t m_resp = 0;
    uint32_t m_sndBuf = 0;
    uint32_t m_rcvBuf = 0;
};

/*
 * The PC's side of the small control requests: a new TCP connection, reqSize bytes, wait for
 * respSize bytes, close.  The latency runs from connect() to the last byte of the answer.
 */
class HttpProbe : public Application
{
  public:
    static TypeId GetTypeId()
    {
        static TypeId tid = TypeId("RackHttpProbe").SetParent<Application>();
        return tid;
    }

    void Setup(Address peer, uint32_t req, uint32_t resp, Time meanPeriod, bool exponential)
    {
        m_peer = peer;
        m_req = req;
        m_resp = resp;
        m_mean = meanPeriod;
        m_exp = exponential;
        m_rng = CreateObject<UniformRandomVariable>();
        m_gap = CreateObject<ExponentialRandomVariable>();
        m_gap->SetAttribute("Mean", DoubleValue(meanPeriod.GetSeconds()));
    }

    std::vector<double> latencyMs; // completed in the window
    uint64_t timeouts = 0;

  private:
    struct Txn
    {
        Time start;
        uint32_t rx = 0;
    };

    void StartApplication() override
    {
        m_next = Simulator::Schedule(Seconds(m_rng->GetValue(0, m_mean.GetSeconds())),
                                     &HttpProbe::Fire, this);
    }

    void StopApplication() override
    {
        m_next.Cancel();
    }

    void Fire()
    {
        Ptr<Socket> s = Socket::CreateSocket(GetNode(), TcpSocketFactory::GetTypeId());
        s->Bind();
        m_open[s] = Txn{Simulator::Now(), 0};
        s->SetConnectCallback(MakeCallback(&HttpProbe::Connected, this),
                              MakeCallback(&HttpProbe::Failed, this));
        s->SetRecvCallback(MakeCallback(&HttpProbe::Recv, this));
        s->Connect(m_peer);
        Simulator::Schedule(Seconds(5), &HttpProbe::Expire, this, s);
        const Time gap = m_exp ? Seconds(m_gap->GetValue()) : m_mean;
        m_next = Simulator::Schedule(gap, &HttpProbe::Fire, this);
    }

    void Connected(Ptr<Socket> s)
    {
        s->Send(Create<Packet>(m_req));
    }

    void Failed(Ptr<Socket> s)
    {
        Expire(s);
    }

    void Recv(Ptr<Socket> s)
    {
        Ptr<Packet> p;
        uint32_t n = 0;
        while ((p = s->Recv()))
        {
            n += p->GetSize();
        }
        auto it = m_open.find(s);
        if (it == m_open.end())
        {
            return;
        }
        it->second.rx += n;
        if (it->second.rx >= m_resp)
        {
            if (it->second.start >= g_start && it->second.start < g_stop)
            {
                latencyMs.push_back((Simulator::Now() - it->second.start).GetSeconds() * 1e3);
            }
            m_open.erase(it);
            s->Close();
        }
    }

    void Expire(Ptr<Socket> s)
    {
        auto it = m_open.find(s);
        if (it == m_open.end())
        {
            return;
        }
        if (it->second.start >= g_start && it->second.start < g_stop)
        {
            timeouts++;
        }
        m_open.erase(it);
        s->Close();
    }

    Address m_peer;
    uint32_t m_req = 0;
    uint32_t m_resp = 0;
    Time m_mean;
    bool m_exp = true;
    EventId m_next;
    std::map<Ptr<Socket>, Txn> m_open;
    Ptr<UniformRandomVariable> m_rng;
    Ptr<ExponentialRandomVariable> m_gap;
};

/*
 * mDNS, as airtime: the AP's side sends a query to the subnet broadcast every period, and each
 * node answers with a broadcast after a random 20-120 ms.  A station's broadcast goes to the AP,
 * which sends it again to everyone at the non-unicast rate: that is what costs airtime.
 */
class MdnsPeer : public Application
{
  public:
    static TypeId GetTypeId()
    {
        static TypeId tid = TypeId("RackMdnsPeer").SetParent<Application>();
        return tid;
    }

    void Setup(Ipv4Address bcast, bool querier, Time period)
    {
        m_bcast = bcast;
        m_querier = querier;
        m_period = period;
        m_rng = CreateObject<UniformRandomVariable>();
    }

  private:
    static constexpr uint16_t kPort = 5353;
    static constexpr uint32_t kQuery = 100;
    static constexpr uint32_t kAnswer = 300;

    void StartApplication() override
    {
        m_sock = Socket::CreateSocket(GetNode(), UdpSocketFactory::GetTypeId());
        m_sock->SetAllowBroadcast(true);
        m_sock->Bind(InetSocketAddress(Ipv4Address::GetAny(), kPort));
        m_sock->SetRecvCallback(MakeCallback(&MdnsPeer::Recv, this));
        if (m_querier)
        {
            m_next = Simulator::Schedule(Seconds(m_rng->GetValue(0, m_period.GetSeconds())),
                                         &MdnsPeer::Query, this);
        }
    }

    void StopApplication() override
    {
        m_next.Cancel();
    }

    void Query()
    {
        m_sock->SendTo(Create<Packet>(kQuery), 0, InetSocketAddress(m_bcast, kPort));
        m_next = Simulator::Schedule(m_period, &MdnsPeer::Query, this);
    }

    void Recv(Ptr<Socket> s)
    {
        Ptr<Packet> p;
        while ((p = s->Recv()))
        {
            if (!m_querier && p->GetSize() == kQuery)
            {
                Simulator::Schedule(MilliSeconds(m_rng->GetInteger(20, 120)), &MdnsPeer::Answer,
                                    this);
            }
        }
    }

    void Answer()
    {
        m_sock->SendTo(Create<Packet>(kAnswer), 0, InetSocketAddress(m_bcast, kPort));
    }

    Ptr<Socket> m_sock;
    Ipv4Address m_bcast;
    bool m_querier = false;
    Time m_period;
    EventId m_next;
    Ptr<UniformRandomVariable> m_rng;
};

/* Channel airtime as a silent station at the rack's centre sees it: time not idle */
Time g_busy;

void
PhyState(Time start, Time duration, WifiPhyState state)
{
    if (state != WifiPhyState::RX && state != WifiPhyState::CCA_BUSY)
    {
        return;
    }
    const Time a = std::max(start, g_start);
    const Time b = std::min(start + duration, g_stop);
    if (b > a)
    {
        g_busy += b - a;
    }
}

std::vector<double> g_pingMs;
uint64_t g_pingTx = 0;

void
PingRtt(uint16_t, Time rtt)
{
    if (InWindow())
    {
        g_pingMs.push_back(rtt.GetSeconds() * 1e3);
    }
}

void
PingTx(uint16_t, Ptr<Packet>)
{
    if (InWindow())
    {
        g_pingTx++;
    }
}

} // namespace

int
main(int argc, char* argv[])
{
    std::string scenario = "ci"; // idle, ci, harsh
    uint32_t active = 8;         // nodes doing USB/IP
    uint32_t bays = 0;           // 0: 8, or 16 when active > 8
    uint32_t cams = 0;           // camera streams (0 .. bays)
    double txPower = 11;         // node TX power, dBm
    double apTxPower = 20;
    double apDist = 2;           // m, from the rack's face
    double extraLoss = 13;       // dB over free space at 1 m: calibrated to the bench's -49 dBm
    bool beacon11b = true;       // AP beacons and broadcasts at 1 Mbit/s DSSS, else 6 Mbit/s OFDM
    std::string usbipDir = "down"; // down: flashing (PC -> node); up: reads (node -> PC)
    double usbipKBps = 362;      // what one node's USB full-speed side can feed
    uint32_t ampduMpdus = 6;     // the ESP32's block-ack window (ESP32_WIFI_TX/RX_BA_WIN)
    uint32_t dutStas = 4;        // harsh: DUTs with their own Wi-Fi, same channel
    double dutMbps = 2;          // each, half up, half down
    double neighbourMbps = 5;    // harsh: a neighbouring BSS, per station (2 stations)
    double simTime = 25;
    double measureFrom = 5;
    uint32_t seed = 1;
    bool header = false;
    bool debug = false;
    double staggerMs = 0; // between two nodes' first flows
    /* Ideal: the best rate for the link SNR.  ns-3's Minstrel-HT left some stations of a
     * 16-node BSS unreachable, idle, with 30+ dB of SNR: a simulator artefact */
    std::string rateManager = "ns3::IdealWifiManager";

    CommandLine cmd(__FILE__);
    cmd.AddValue("scenario", "idle, ci or harsh", scenario);
    cmd.AddValue("active", "nodes doing USB/IP", active);
    cmd.AddValue("bays", "bays in the rack (0: 8, 16 above 8 active)", bays);
    cmd.AddValue("cams", "camera streams", cams);
    cmd.AddValue("txPower", "node TX power, dBm", txPower);
    cmd.AddValue("apTxPower", "AP TX power, dBm", apTxPower);
    cmd.AddValue("apDist", "AP distance from the rack, m", apDist);
    cmd.AddValue("extraLoss", "extra path loss at 1 m, dB", extraLoss);
    cmd.AddValue("beacon11b", "beacons and broadcasts at 1 Mbit/s", beacon11b);
    cmd.AddValue("usbipDir", "down (flashing) or up (reads)", usbipDir);
    cmd.AddValue("usbipKBps", "USB/IP rate a node can feed, kB/s", usbipKBps);
    cmd.AddValue("ampduMpdus", "MPDUs per A-MPDU", ampduMpdus);
    cmd.AddValue("dutStas", "harsh: DUT stations with their own Wi-Fi", dutStas);
    cmd.AddValue("dutMbps", "harsh: each DUT's traffic, Mbit/s", dutMbps);
    cmd.AddValue("neighbourMbps", "harsh: neighbouring BSS, Mbit/s per station", neighbourMbps);
    cmd.AddValue("simTime", "simulated time, s", simTime);
    cmd.AddValue("measureFrom", "start of the measurement window, s", measureFrom);
    cmd.AddValue("seed", "RNG run", seed);
    cmd.AddValue("header", "print the CSV header and exit", header);
    cmd.AddValue("debug", "per-bay details on stderr", debug);
    cmd.AddValue("staggerMs", "delay between two nodes' flows starting, ms", staggerMs);
    cmd.AddValue("rateManager", "rate control of the rack BSS", rateManager);
    cmd.Parse(argc, argv);

    if (header)
    {
        std::cout << "scenario,bays,active,cams,txPower,apDist,beacon11b,usbipDir,ampduMpdus,seed,assoc,stas,dead,"
                     "airtime_pct,ping_p50_ms,ping_p95_ms,ping_p99_ms,ping_loss_pct,"
                     "http_n,http_p50_ms,http_p95_ms,http_p99_ms,http_timeouts,"
                     "scrape_p95_ms,mac_ok,mac_retx,mac_fail,mac_retx_pct,"
                     "tcp_segs,tcp_retx,tcp_retx_pct,usbip_offered_kBps,usbip_goodput_kBps,"
                     "usbip_goodput_min_kBps,cam_fps,cam_skipped_pct,cam_kBps,"
                     "dut_goodput_Mbps,neighbour_goodput_Mbps,wall_s\n";
        return 0;
    }

    const auto wallStart = std::chrono::steady_clock::now();
    RngSeedManager::SetSeed(1);
    RngSeedManager::SetRun(seed);
    g_start = Seconds(measureFrom);
    g_stop = Seconds(simTime);

    if (bays == 0)
    {
        bays = active > 8 ? 16 : 8;
    }
    if (scenario == "idle")
    {
        active = 0;
        cams = 0;
    }
    active = std::min(active, bays);
    cams = std::min(cams, bays);
    const bool harsh = scenario == "harsh";

    /* Zephyr on the node: 21 KB of TCP send window (NET_BUF_TX_COUNT), about 12 KB to receive */
    const uint32_t nodeSnd = 21 * 1024;
    const uint32_t nodeRcv = 12 * 1024;
    const uint32_t pcBuf = 256 * 1024;
    Config::SetDefault("ns3::TcpSocket::SegmentSize", UintegerValue(1448));
    Config::SetDefault("ns3::TcpSocket::SndBufSize", UintegerValue(pcBuf));
    Config::SetDefault("ns3::TcpSocket::RcvBufSize", UintegerValue(pcBuf));

    /* --- nodes */
    NodeContainer bayNodes;
    bayNodes.Create(bays);
    NodeContainer hub;
    hub.Create(1);
    NodeContainer ap;
    ap.Create(1);
    NodeContainer pc;
    pc.Create(1);
    NodeContainer monitor;
    monitor.Create(1);
    NodeContainer dutAp;
    NodeContainer duts;
    NodeContainer nbAp;
    NodeContainer nbStas;
    if (harsh)
    {
        dutAp.Create(1);
        duts.Create(dutStas);
        nbAp.Create(1);
        nbStas.Create(2);
    }

    /* --- positions: 4 columns 165.8 mm apart, rows 165 mm apart, the AP in front */
    const double colPitch = 0.1658;
    const double rowPitch = 0.165;
    const uint32_t rows = (bays + 3) / 4;
    const double cx = 1.5 * colPitch;
    const double cz = 0.5 * (rows - 1) * rowPitch;
    Ptr<ListPositionAllocator> pos = CreateObject<ListPositionAllocator>();
    for (uint32_t i = 0; i < bays; i++)
    {
        pos->Add(Vector((i % 4) * colPitch, 0, (i / 4) * rowPitch));
    }
    pos->Add(Vector(cx, 0.05, -0.08)); // the hub, under row A
    pos->Add(Vector(cx, -apDist, cz)); // the AP
    pos->Add(Vector(cx, -apDist, cz)); // the PC: wired, its position is irrelevant
    pos->Add(Vector(cx, 0.02, cz));    // the monitor
    if (harsh)
    {
        pos->Add(Vector(cx + 1.0, -2.0, cz)); // the DUTs' lab AP
        for (uint32_t i = 0; i < dutStas; i++)
        {
            pos->Add(Vector((i % 4) * colPitch + 0.05, 0.08, (i / 4) * rowPitch));
        }
        pos->Add(Vector(cx, 12.0, cz)); // a neighbour's AP, through a wall
        pos->Add(Vector(cx - 2.0, 13.0, cz));
        pos->Add(Vector(cx + 2.0, 11.0, cz));
    }
    NodeContainer all;
    all.Add(bayNodes);
    all.Add(hub);
    all.Add(ap);
    all.Add(pc);
    all.Add(monitor);
    all.Add(dutAp);
    all.Add(duts);
    all.Add(nbAp);
    all.Add(nbStas);
    MobilityHelper mob;
    mob.SetPositionAllocator(pos);
    mob.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mob.Install(all);

    /* --- the channel */
    YansWifiChannelHelper chan;
    chan.SetPropagationDelay("ns3::ConstantSpeedPropagationDelayModel");
    chan.AddPropagationLoss("ns3::LogDistancePropagationLossModel", "Exponent", DoubleValue(3.0),
                            "ReferenceDistance", DoubleValue(1.0), "ReferenceLoss",
                            DoubleValue(46.68 + extraLoss));
    Ptr<YansWifiChannel> channel = chan.Create();

    YansWifiPhyHelper phy;
    phy.SetChannel(channel);
    phy.Set("ChannelSettings", StringValue("{6, 20, BAND_2_4GHZ, 0}"));

    WifiHelper wifi;
    wifi.SetStandard(WIFI_STANDARD_80211n);
    const std::string nonUnicast = beacon11b ? "DsssRate1Mbps" : "ErpOfdmRate6Mbps";
    WifiMacHelper mac;
    const Ssid rackSsid("rack");

    phy.Set("TxPowerStart", DoubleValue(txPower));
    phy.Set("TxPowerEnd", DoubleValue(txPower));
    wifi.SetRemoteStationManager(rateManager);
    mac.SetType("ns3::StaWifiMac", "Ssid", SsidValue(rackSsid), "ActiveProbing",
                BooleanValue(false));
    NodeContainer stas;
    stas.Add(bayNodes);
    stas.Add(hub);
    NetDeviceContainer staDevs = wifi.Install(phy, mac, stas);

    phy.Set("TxPowerStart", DoubleValue(apTxPower));
    phy.Set("TxPowerEnd", DoubleValue(apTxPower));
    wifi.SetRemoteStationManager(rateManager, "NonUnicastMode",
                                 StringValue(nonUnicast));
    mac.SetType("ns3::ApWifiMac", "Ssid", SsidValue(rackSsid));
    NetDeviceContainer apDev = wifi.Install(phy, mac, ap);
    if (!beacon11b)
    {
        /* Management frames (beacons) go at the first basic rate, DSSS 1 Mbit/s unless the basic
         * set starts with OFDM 6 Mbit/s: an AP with 11b off.  Before any station associates. */
        Ptr<WifiRemoteStationManager> m =
            DynamicCast<WifiNetDevice>(apDev.Get(0))->GetRemoteStationManager();
        Simulator::Schedule(MilliSeconds(1), [m]() {
            m->Reset();
            m->AddBasicMode(WifiMode("ErpOfdmRate6Mbps"));
        });
    }

    mac.SetType("ns3::AdhocWifiMac");
    wifi.SetRemoteStationManager(rateManager);
    NetDeviceContainer monDev = wifi.Install(phy, mac, monitor);

    NetDeviceContainer dutDevs;
    NetDeviceContainer dutApDev;
    NetDeviceContainer nbDevs;
    NetDeviceContainer nbApDev;
    if (harsh)
    {
        /* the DUTs' own radios at full power, their AP and the neighbour's with 11b beacons */
        phy.Set("TxPowerStart", DoubleValue(20));
        phy.Set("TxPowerEnd", DoubleValue(20));
        wifi.SetRemoteStationManager(rateManager);
        mac.SetType("ns3::StaWifiMac", "Ssid", SsidValue(Ssid("lab")), "ActiveProbing",
                    BooleanValue(false));
        dutDevs = wifi.Install(phy, mac, duts);
        mac.SetType("ns3::StaWifiMac", "Ssid", SsidValue(Ssid("neighbour")), "ActiveProbing",
                    BooleanValue(false));
        nbDevs = wifi.Install(phy, mac, nbStas);
        wifi.SetRemoteStationManager(rateManager, "NonUnicastMode",
                                     StringValue("DsssRate1Mbps"));
        mac.SetType("ns3::ApWifiMac", "Ssid", SsidValue(Ssid("lab")));
        dutApDev = wifi.Install(phy, mac, dutAp);
        mac.SetType("ns3::ApWifiMac", "Ssid", SsidValue(Ssid("neighbour")));
        nbApDev = wifi.Install(phy, mac, nbAp);
    }

    /* A-MPDUs no longer than the ESP32's block-ack window, both ways */
    const uint32_t ampdu = ampduMpdus * 1600;
    for (auto devs : {staDevs, apDev})
    {
        for (uint32_t i = 0; i < devs.GetN(); i++)
        {
            devs.Get(i)->GetObject<WifiNetDevice>()->GetMac()->SetAttribute(
                "BE_MaxAmpduSize", UintegerValue(ampdu));
        }
    }

    /* --- IP: the Wi-Fi subnet, the PC behind the AP on a gigabit link */
    PointToPointHelper p2p;
    p2p.SetDeviceAttribute("DataRate", StringValue("1Gbps"));
    p2p.SetChannelAttribute("Delay", StringValue("50us"));
    NetDeviceContainer wired = p2p.Install(pc.Get(0), ap.Get(0));

    InternetStackHelper ip;
    ip.Install(all);
    Ipv4AddressHelper addr;
    addr.SetBase("10.1.0.0", "255.255.0.0");
    NetDeviceContainer rackDevs;
    rackDevs.Add(staDevs);
    rackDevs.Add(apDev);
    Ipv4InterfaceContainer rackIf = addr.Assign(rackDevs);
    addr.SetBase("10.2.0.0", "255.255.255.0");
    Ipv4InterfaceContainer wiredIf = addr.Assign(wired);
    Ipv4InterfaceContainer dutIf;
    Ipv4InterfaceContainer dutApIf;
    Ipv4InterfaceContainer nbIf;
    Ipv4InterfaceContainer nbApIf;
    if (harsh)
    {
        addr.SetBase("10.4.0.0", "255.255.255.0");
        dutIf = addr.Assign(dutDevs);
        dutApIf = addr.Assign(dutApDev);
        addr.SetBase("10.5.0.0", "255.255.255.0");
        nbIf = addr.Assign(nbDevs);
        nbApIf = addr.Assign(nbApDev);
    }
    /* Static routes: global routing would take the BSSs sharing the channel for one link */
    Ipv4StaticRoutingHelper routes;
    const Ipv4Address apAddr = rackIf.GetAddress(rackIf.GetN() - 1);
    for (uint32_t i = 0; i < stas.GetN(); i++)
    {
        routes.GetStaticRouting(stas.Get(i)->GetObject<Ipv4>())->SetDefaultRoute(apAddr, 1);
    }
    routes.GetStaticRouting(pc.Get(0)->GetObject<Ipv4>())
        ->SetDefaultRoute(wiredIf.GetAddress(1), 1);
    const Ipv4Address pcAddr = wiredIf.GetAddress(0);
    const Ipv4Address bcast("10.1.255.255");
    /* ARP is done once in a real rack: start with full caches, so that a lost broadcast ARP
     * request under load does not stall a flow for seconds */
    NeighborCacheHelper neighbours;
    neighbours.PopulateNeighborCache();

    /* --- the rack's traffic */
    const Time appStart = Seconds(2);
    const Time appStop = Seconds(simTime);
    uint16_t port = 10000;
    std::vector<Ptr<StreamSender>> usbipTx;
    std::vector<Ptr<CountingSink>> usbipRx;
    std::vector<Ptr<StreamSender>> camTx;
    std::vector<Ptr<CountingSink>> camRx;
    std::vector<Ptr<HttpProbe>> probes;
    std::vector<Ptr<HttpProbe>> scrapes;
    Time flowStart = appStart;

    auto stream = [&](Ptr<Node> from, Ptr<Node> to, Ipv4Address toAddr, bool fromIsNode,
                      uint32_t chunk, Time period, uint32_t fMin, uint32_t fMax,
                      uint32_t backlog) {
        auto rx = CreateObject<CountingSink>();
        rx->Setup(port, fromIsNode ? pcBuf : nodeSnd, fromIsNode ? pcBuf : nodeRcv);
        to->AddApplication(rx);
        rx->SetStartTime(Seconds(1));
        rx->SetStopTime(appStop);
        auto tx = CreateObject<StreamSender>();
        tx->Setup(InetSocketAddress(toAddr, port), chunk, period, fMin, fMax, backlog,
                  fromIsNode ? nodeSnd : pcBuf, fromIsNode ? nodeRcv : pcBuf);
        from->AddApplication(tx);
        tx->SetStartTime(flowStart);
        tx->SetStopTime(appStop);
        port++;
        return std::make_pair(tx, rx);
    };

    const uint32_t urb = 4096;
    const Time urbPeriod = Seconds(urb / (usbipKBps * 1000.0));
    for (uint32_t i = 0; i < bays; i++)
    {
        Ptr<Node> n = bayNodes.Get(i);
        const Ipv4Address na = rackIf.GetAddress(i);
        flowStart = appStart + MilliSeconds(staggerMs * i);
        /* the node's web server: status page and API on 80, /metrics on 9100 */
        auto web = CreateObject<HttpServer>();
        web->Setup(80, 200, 600, nodeSnd, nodeRcv);
        n->AddApplication(web);
        auto metrics = CreateObject<HttpServer>();
        metrics->Setup(9100, 150, 2048, nodeSnd, nodeRcv);
        n->AddApplication(metrics);
        auto probe = CreateObject<HttpProbe>();
        probe->Setup(InetSocketAddress(na, 80), 200, 600, Seconds(1), true);
        pc.Get(0)->AddApplication(probe);
        probe->SetStartTime(appStart);
        probe->SetStopTime(appStop);
        probes.push_back(probe);
        auto scrape = CreateObject<HttpProbe>();
        scrape->Setup(InetSocketAddress(na, 9100), 150, 2048, Seconds(15), false);
        pc.Get(0)->AddApplication(scrape);
        scrape->SetStartTime(appStart);
        scrape->SetStopTime(appStop);
        scrapes.push_back(scrape);

        if (i < active)
        {
            /* USB/IP: 4 KB URBs at what the node's USB side can feed */
            auto f = usbipDir == "down"
                         ? stream(pc.Get(0), n, na, false, urb, urbPeriod, 0, 0, 4 * urb)
                         : stream(n, pc.Get(0), pcAddr, true, urb, urbPeriod, 0, 0, 4 * urb);
            usbipTx.push_back(f.first);
            usbipRx.push_back(f.second);
            /* the URBs' replies the other way, and the DUT's console (2 kB/s) */
            if (usbipDir == "down")
            {
                stream(n, pc.Get(0), pcAddr, true, 48, urbPeriod, 0, 0, 64 * 48);
            }
            else
            {
                stream(pc.Get(0), n, na, false, 48, urbPeriod, 0, 0, 64 * 48);
            }
            stream(n, pc.Get(0), pcAddr, true, 64, MilliSeconds(32), 0, 0, 4096);
        }
        if (i < cams)
        {
            /* MJPEG: 5 frames/s of 30-60 KB, skipped while the previous is still queued */
            auto f = stream(n, pc.Get(0), pcAddr, true, 0, MilliSeconds(200), 30000, 60000, 0);
            camTx.push_back(f.first);
            camRx.push_back(f.second);
        }
    }
    /* the hub: polled and scraped like a node */
    {
        const Ipv4Address ha = rackIf.GetAddress(bays);
        auto web = CreateObject<HttpServer>();
        web->Setup(80, 150, 2048, nodeSnd, nodeRcv);
        hub.Get(0)->AddApplication(web);
        auto scrape = CreateObject<HttpProbe>();
        scrape->Setup(InetSocketAddress(ha, 80), 150, 2048, Seconds(15), false);
        pc.Get(0)->AddApplication(scrape);
        scrape->SetStartTime(appStart);
        scrape->SetStopTime(appStop);
    }

    /* mDNS: a query every 10 s, every node and the hub answer */
    {
        auto q = CreateObject<MdnsPeer>();
        q->Setup(bcast, true, Seconds(10));
        ap.Get(0)->AddApplication(q);
        q->SetStartTime(appStart);
        q->SetStopTime(appStop);
        for (uint32_t i = 0; i < stas.GetN(); i++)
        {
            auto a = CreateObject<MdnsPeer>();
            a->Setup(bcast, false, Seconds(10));
            stas.Get(i)->AddApplication(a);
            a->SetStartTime(Seconds(1));
            a->SetStopTime(appStop);
        }
    }

    /* ping from the PC to every node, every 500 ms */
    for (uint32_t i = 0; i < bays; i++)
    {
        PingHelper ping(rackIf.GetAddress(i));
        ping.SetAttribute("Interval", TimeValue(MilliSeconds(500)));
        ping.SetAttribute("Size", UintegerValue(56));
        ping.SetAttribute("VerboseMode", EnumValue(Ping::VerboseMode::SILENT));
        ApplicationContainer a = ping.Install(pc.Get(0));
        a.Start(appStart + MilliSeconds(37 * i));
        a.Stop(appStop);
        a.Get(0)->TraceConnectWithoutContext("Rtt", MakeCallback(&PingRtt));
        a.Get(0)->TraceConnectWithoutContext("Tx", MakeCallback(&PingTx));
    }

    /* harsh: the DUTs' own Wi-Fi traffic and the neighbour's, constant-rate UDP */
    std::vector<Ptr<PacketSink>> harshSinks;
    std::vector<bool> harshIsDut;
    if (harsh)
    {
        auto udp = [&](Ptr<Node> from, Ptr<Node> to, Ipv4Address toAddr, double mbps,
                       bool isDut) {
            PacketSinkHelper sink("ns3::UdpSocketFactory",
                                  InetSocketAddress(Ipv4Address::GetAny(), port));
            ApplicationContainer s = sink.Install(to);
            s.Start(Seconds(1));
            s.Stop(appStop);
            OnOffHelper onoff("ns3::UdpSocketFactory", InetSocketAddress(toAddr, port));
            onoff.SetConstantRate(DataRate(static_cast<uint64_t>(mbps * 1e6)), 1000);
            ApplicationContainer c = onoff.Install(from);
            c.Start(appStart);
            c.Stop(appStop);
            harshSinks.push_back(DynamicCast<PacketSink>(s.Get(0)));
            harshIsDut.push_back(isDut);
            port++;
        };
        for (uint32_t i = 0; i < dutStas; i++)
        {
            udp(duts.Get(i), dutAp.Get(0), dutApIf.GetAddress(0), dutMbps / 2, true);
            udp(dutAp.Get(0), duts.Get(i), dutIf.GetAddress(i), dutMbps / 2, true);
        }
        for (uint32_t i = 0; i < nbStas.GetN(); i++)
        {
            udp(nbAp.Get(0), nbStas.Get(i), nbIf.GetAddress(i), neighbourMbps, false);
        }
    }

    /* --- what is measured */
    monDev.Get(0)->GetObject<WifiNetDevice>()->GetPhy()->GetState()->TraceConnectWithoutContext(
        "State", MakeCallback(&PhyState));
    WifiTxStatsHelper txStats(g_start, g_stop);
    txStats.Enable(rackDevs);
    std::vector<uint64_t> harshAtStart(harshSinks.size(), 0);
    uint32_t associated = 0;
    Simulator::Schedule(g_start, [&]() {
        for (uint32_t i = 0; i < staDevs.GetN(); i++)
        {
            auto sta = DynamicCast<StaWifiMac>(
                DynamicCast<WifiNetDevice>(staDevs.Get(i))->GetMac());
            const bool both = sta->IsAssociated() &&
                              DynamicCast<ApWifiMac>(
                                  DynamicCast<WifiNetDevice>(apDev.Get(0))->GetMac())
                                  ->IsAssociated(sta->GetAddress())
                                  .has_value();
            associated += both ? 1 : 0;
        }
        for (size_t i = 0; i < harshSinks.size(); i++)
        {
            harshAtStart[i] = harshSinks[i]->GetTotalRx();
        }
    });

    Simulator::Stop(Seconds(simTime));
    Simulator::Run();

    /* --- one CSV line */
    const double win = (g_stop - g_start).GetSeconds();
    std::vector<double> http;
    uint64_t httpTimeouts = 0;
    for (auto& p : probes)
    {
        http.insert(http.end(), p->latencyMs.begin(), p->latencyMs.end());
        httpTimeouts += p->timeouts;
    }
    std::vector<double> scrape;
    for (auto& p : scrapes)
    {
        scrape.insert(scrape.end(), p->latencyMs.begin(), p->latencyMs.end());
    }
    double offered = 0;
    double goodput = 0;
    double goodMin = NAN;
    for (size_t i = 0; i < usbipRx.size(); i++)
    {
        offered += usbipTx[i]->offered / win / 1e3;
        const double g = usbipRx[i]->received / win / 1e3;
        goodput += g;
        goodMin = std::isnan(goodMin) ? g : std::min(goodMin, g);
    }
    const double nU = usbipRx.empty() ? NAN : usbipRx.size();
    double camFps = 0;
    double camSkip = 0;
    double camKBps = 0;
    for (size_t i = 0; i < camRx.size(); i++)
    {
        camFps += camTx[i]->framesIn / win;
        const double tot = camTx[i]->framesIn + camTx[i]->framesSkipped;
        camSkip += tot > 0 ? 100.0 * camTx[i]->framesSkipped / tot : 0;
        camKBps += camRx[i]->received / win / 1e3;
    }
    const double nC = camRx.empty() ? NAN : camRx.size();
    double dutGood = 0;
    double nbGood = 0;
    for (size_t i = 0; i < harshSinks.size(); i++)
    {
        const double mbps = (harshSinks[i]->GetTotalRx() - harshAtStart[i]) * 8 / win / 1e6;
        (harshIsDut[i] ? dutGood : nbGood) += mbps;
    }
    /* A station whose every MPDU fails while it and the AP hold the association: an ns-3 corner
     * case of some seeds at 12+ nodes (docs/wifi-capacity-ns3.md); summarize.py drops such runs */
    uint32_t dead = 0;
    {
        const auto ok = txStats.GetSuccessesByNodeDevice();
        const auto fail = txStats.GetFailuresByNodeDevice();
        for (uint32_t i = 0; i < stas.GetN(); i++)
        {
            const auto key = std::make_pair(stas.Get(i)->GetId(), 0U);
            if ((ok.count(key) ? ok.at(key) : 0) == 0 && (fail.count(key) ? fail.at(key) : 0) > 0)
            {
                dead++;
            }
        }
    }
    const uint64_t macOk = txStats.GetSuccesses();
    const uint64_t macRetx = txStats.GetRetransmissions();
    const uint64_t macFail = txStats.GetFailures();
    const double wall =
        std::chrono::duration<double>(std::chrono::steady_clock::now() - wallStart).count();
    if (debug)
    {
        for (uint32_t i = 0; i < bays; i++)
        {
            const Vector p = bayNodes.Get(i)->GetObject<MobilityModel>()->GetPosition();
            {
                const auto ok = txStats.GetSuccessesByNodeDevice();
                const auto fail = txStats.GetFailuresByNodeDevice();
                const auto key = std::make_pair(bayNodes.Get(i)->GetId(), 0U);
                std::cerr << "mac ok " << (ok.count(key) ? ok.at(key) : 0) << " fail "
                          << (fail.count(key) ? fail.at(key) : 0) << " | ";
            }
            std::cerr << "bay " << i << " " << rackIf.GetAddress(i) << " pos " << p.x << ","
                      << p.y << "," << p.z << " probes " << probes[i]->latencyMs.size()
                      << " timeouts " << probes[i]->timeouts;
            if (i < usbipRx.size())
            {
                std::cerr << " usbip " << usbipRx[i]->received / win / 1e3 << " kB/s, first byte "
                          << usbipRx[i]->firstRx.GetSeconds() << " s";
            }
            std::cerr << "\n";
        }
    }

    std::cout << scenario << "," << bays << "," << active << "," << cams << "," << txPower << ","
              << apDist << "," << (beacon11b ? 1 : 0) << "," << usbipDir << "," << ampduMpdus
              << "," << seed << ","
              << associated << "," << staDevs.GetN() << "," << dead << ","
              << 100.0 * g_busy.GetSeconds() / win << "," << Percentile(g_pingMs, 0.5) << ","
              << Percentile(g_pingMs, 0.95) << "," << Percentile(g_pingMs, 0.99) << ","
              << (g_pingTx ? 100.0 * (1.0 - double(g_pingMs.size()) / g_pingTx) : NAN) << ","
              << http.size() << "," << Percentile(http, 0.5) << "," << Percentile(http, 0.95)
              << "," << Percentile(http, 0.99) << "," << httpTimeouts << ","
              << Percentile(scrape, 0.95) << "," << macOk << "," << macRetx << "," << macFail
              << "," << (macOk ? 100.0 * macRetx / (macOk + macFail) : NAN) << "," << g_tcpSegs
              << "," << g_tcpRetx << ","
              << (g_tcpSegs ? 100.0 * g_tcpRetx / g_tcpSegs : NAN) << "," << offered / nU << ","
              << goodput / nU << "," << goodMin << "," << camFps / nC << "," << camSkip / nC
              << "," << camKBps / nC << "," << dutGood << "," << nbGood << "," << wall << "\n";

    Simulator::Destroy();
    return 0;
}
