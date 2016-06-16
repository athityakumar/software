// ASLAM Implementation
// Written by Christopher Goes (cwg46@cornell.edu)
// Last Update 11 April 2014

// Implementation Conventions:
// First dimension - north, second dimension - east.

#include<string>
#include<cstdlib>
#include<iostream>
#include<cmath>
#include<algorithm>

#include <sys/time.h>

#include "aslam.h"

#define DEFAULT_XMAX 50
#define DEFAULT_YMAX 50
#define HEADING_REJECT_THRESHOLD 10 // degrees
#define DISTANCE_REJECT_THRESHOLD 20 // percent
#define TIME_DECAY_CONSTANT 0.0001

#define SIGMA_INCLUDE 0.682689492137086
#define PI 3.141592653589793238462643383279502
#define E 2.718281828459045

using std::vector;
using std::cout;
using std::cin;
using std::endl;
using std::pow;
using std::exp;
using std::sqrt;
using std::pair;
using std::sort;
using std::move;

static void log(string message) {
#ifdef _LOG_
    cout << message << endl;
#endif
}

static void debug(string message) {
#ifdef _DEBUG_
    cout << message << endl;
#endif
}

static double time() {
    timeval tv;
    gettimeofday(&tv, NULL);
    return tv.tv_sec + tv.tv_usec / 1000000.;
}

static double gaussian(double mu, double sigma, double x) {
    return exp(-pow(x - mu, 2) / (2*pow(sigma, 2)));
}

// Relative to <1, 0> i.e. north
static double toHeading(double n, double e) {
    double result = atan(e / n) * 180. / PI;
    if (n > 0 && e > 0) result = result;
    else if (n < 0 && e > 0) result += 180;
    else if (n < 0 && e < 0) result += 180;
    else if (n > 0 && e < 0) result += 360;
    //return result;
    result = 90 - result;
    if (result < 0) result += 360;
    return result;
}

static double toDistance(double n, double e) { return sqrt(pow(n, 2) + pow(e, 2)); }

Matrix::Matrix() : Matrix(1.) {}

Matrix::Matrix(double initialValue) : Matrix(DEFAULT_XMAX, DEFAULT_YMAX, initialValue) {}

Matrix::Matrix(double xMax, double yMax, double initialValue)/* : vals(256, vector<double> (256)) */{
    vals.resize(DIMX);
    xScale = xMax / DIMX;
    yScale = yMax / DIMY;
    for (int x = 0; x < DIMX; x++) { vals[x].resize(DIMY); for (int y = 0; y < DIMY; y++) { vals[x][y] = initialValue; } }
    normalize();
}
/*
Matrix::Matrix(const Matrix& other) {
    xScale = other.xScale;
    yScale = other.yScale;
    for (int x = 0; x < DIMX; x++) { double temp .at(DIMX); memcpy(other.vals[x], temp, DIMY * sizeof(double)); vals[x] = temp; }
}

Matrix& Matrix::operator=(const Matrix& m) {
    if (this != &m) {
        for (int x = 0; x < DIMX; x++) { double temp .at(DIMX); memcpy(m.vals[x], temp, DIMY * sizeof(double)); vals[x] = temp; }
    }
    return *this;
}*/

//Matrix::~Matrix() { 
//    for(int x = 0; x < DIMX; x++) { delete[] vals[x]; } delete[] vals; 
//    for(int x = 0; x < DIMX; x++) { for (int y = 0; y < DIMY; y++) { delete &vals[x][y]; }}
//}

void Matrix::update(shared_ptr<Function> f) {
    for (int x = 0; x < DIMX; x++) { for (int y = 0; y < DIMY; y++) { vals[x][y] = vals[x][y] * f->call(x*xScale, y*yScale); } }
    normalize();
}

/* Uses scale of FIRST matrix. */
shared_ptr<Matrix> Matrix::operator*(shared_ptr<Matrix> m) {
    shared_ptr<Matrix> n (new Matrix(xScale * DIMX, yScale * DIMY, 1.));
    for (int x = 0; x < DIMX; x++) { for (int y = 0; y < DIMY; y++) { n->vals[x][y] = (vals[x][y] * m->vals[x][y]); } }
    n->normalize();
    return n;
}

shared_ptr<Matrix> Matrix::operator^(double p) {
    shared_ptr<Matrix> n (new Matrix(xScale * DIMX, yScale * DIMY, 1.));
    for (int x = 0; x < DIMX; x++) { for (int y = 0; y < DIMY; y++) { n->vals[x][y] = pow(vals[x][y], p); } }
    n->normalize();
    return n;
}

void Matrix::operator*=(Matrix m) {
    for (int x = 0; x < DIMX; x++) { for (int y = 0; y < DIMY; y++) { vals[x][y] = vals[x][y] * m.vals[x][y]; } }
//    for (int x = 0; x < DIMX; x++) { for (int y = 0; y < DIMY; y++) { cout << vals[x][y] * m->vals[x][y] << endl; } }
    normalize();
}

void Matrix::centroid() { 
    double xsum, ysum;
    for (int x = 0; x < DIMX; x++) { for (int y = 0; y < DIMY; y++) { xsum += x*vals[x][y]; ysum += y*vals[x][y]; } }
    centn = xsum * xScale;
    cente = ysum * xScale;
}

// 1 sigma - minimum distance at which ~68.27% probability is inside
void Matrix::error() {
    vector<shared_ptr<tuple<double>>> vtemp;
    for (int x = 0; x < DIMX; x++) { for (int y = 0; y < DIMY; y++) {
        shared_ptr<tuple<double>> t (new tuple<double>());
        t->v1 = toDistance(x * xScale - centn, y * yScale - cente);
        t->v2 = vals[x][y];
        vtemp.push_back(t);
    } }
    sort(vtemp.begin(), vtemp.end(), [] (shared_ptr<tuple<double>> t1, shared_ptr<tuple<double>> t2) { return t1->v1 < t2->v1; });
    double sum = 0.;
    int i = -1;
    while (sum < SIGMA_INCLUDE) {
        i++;
        sum += vtemp[i]->v2;
    }
    err = vtemp[i]->v1;
}

void Matrix::normalize() { 
    double sum = 0; 
    for (int x = 0; x < DIMX; x++) { for (int y = 0; y < DIMY; y++) { sum += vals[x][y]; } }
    if (sum == 0.) return;
    for (int x = 0; x < DIMX; x++) { for (int y = 0; y < DIMY; y++) { vals[x][y] = vals[x][y] / sum; } }
}

State::State(double initN, double initE, double initErr) {
    addObject("sub", initN, initE, initErr);
    update();
}

class OIF : public Function {
    public:
        double call(double n, double e) { return gaussian(0., err, toDistance(n - centn, e - cente)); }
        double centn, cente, err;
};

void State::addObject(string identifier, double n, double e, double err) {
    shared_ptr<Event> nevent (new Event());
    nevent->time = time();
    shared_ptr<OIF> eim (new OIF());
    eim->centn = n;
    eim->cente = e;
    eim->err = err;
    nevent->eum = shared_ptr<Matrix>(new Matrix(1.));
    nevent->eum->update(eim);
    shared_ptr<Object> nobject (new Object());
    nobject->events.push_back(nevent);
    nobject->pmap = shared_ptr<Matrix>(new Matrix(1.));
    objects[identifier] = nobject;
}

class HUF : public Function {
    public:
        double call(double n, double e) { return gaussian(heading, err, toHeading(n - o->centn, e - o->cente)); }
        shared_ptr<Object> o;
        double heading, err;
};

bool State::hObs(string o1i, string o2i, double heading, double err) {
    double prevn = objects[o2i]->centn;
    double preve = objects[o2i]->cente;
    
    // Input rejection.
    double expHeading = toHeading(objects[o2i]->centn - objects[o1i]->cente, objects[o2i]->centn - objects[o1i]->cente);
    if (abs(heading - expHeading) > HEADING_REJECT_THRESHOLD) return false;

    // Bayesian update.
    shared_ptr<Event> e (new Event());
    e->time = time();
    e->eum = shared_ptr<Matrix> (new Matrix(1.));
    shared_ptr<HUF> f (new HUF());
    f->o = objects[o1i];
    f->heading = heading;
    f->err = err;
    e->eum->update(f);
    objects[o2i]->events.push_back(e);

    // Error estimation.
    triple<double> t;
    t.v1 = expHeading;
    t.v2 = heading;
    t.v3 = err;
    headingErrors.push_back(t);

    // Covariance
    update();
    doCovariance(o2i, prevn, preve, err);
    return true;
}

class DUF : public Function {
    public:
        double call(double n, double e) { return gaussian(distance, err, toDistance(n - o->centn, e - o->cente)); }
        shared_ptr<Object> o;
        double distance, err;
};

bool State::dObs(string o1i, string o2i, double distance, double err) {
    double prevn = objects[o2i]->centn;
    double preve = objects[o2i]->cente;

    // Input rejection.
    double expDistance = toDistance(objects[o2i]->centn - objects[o1i]->cente, objects[o2i]->centn - objects[o1i]->cente);
    if (abs(distance - expDistance) / distance > DISTANCE_REJECT_THRESHOLD) return false;

    // Bayesian update.
    shared_ptr<Event> e (new Event());
    e->time = time();
    e->eum = shared_ptr<Matrix> (new Matrix(1.));
    shared_ptr<DUF> f (new DUF());
    f->o = objects[o1i];
    f->distance = distance;
    f->err = err;
    e->eum->update(f);
    objects[o2i]->events.push_back(e);

    // Error estimation.
    triple<double> t;
    t.v1 = expDistance;
    t.v2 = distance;
    t.v3 = err;
    distanceErrors.push_back(t);
   
    // Covariance
    update();
    doCovariance(o2i, prevn, preve, err);
    return true;
}

void State::move(double deltaX, double deltaY, double err) {
/*    shared_ptr<Matrix> tpmap(new Matrix());
    for (int tx = 0; tx < DIMX; tx++) { for (int ty = 0; ty < DIMY; ty++) { tpmap->vals[tx][ty] = 0.; } }
    for (int x = 0; x < DIMX; x++) { for (int y = 0; y < DIMY; y++) {
        int ax = (int) (x - (deltaX / objects["sub"]->pmap->xScale));
        int ay = (int) (y - (deltaY / objects["sub"]->pmap->yScale));
        if (0 > ax || 0 > ay || ax >= DIMX || 0 > ay >= DIMY) continue;
        for (int tx = 0; tx < DIMX; tx++) { for (int ty = 0; ty < DIMY; ty++) {
            tpmap->vals[tx][ty] = tpmap->vals[tx][ty] + objects["sub"]->pmap->vals[ax][ay] * gaussian(0., err, toDistance((tx - ax) * objects["sub"]->pmap->xScale, (ty - ay) * objects["sub"]->pmap->yScale));
        tpmap->vals[x][y] = objects["sub"]->pmap->vals[ax][ay];
    } }*/
    objects["sub"]->centn_offset += deltaX;
    objects["sub"]->cente_offset += deltaY;
    
}

void State::update() { 
    for (pair<const string, shared_ptr<Object>> kv : objects) {
        shared_ptr<Object> o = kv.second;
        o->pmap = shared_ptr<Matrix>(new Matrix(1.));
        double t = time();
        for (shared_ptr<Event> e : o->events) {
            double factor = pow(E, (TIME_DECAY_CONSTANT * (e->time - t)));
            *o->pmap *= *(*e->eum ^ factor); // time decay, with overloaded operators to boot!
        }

        o->pmap->centroid();
        o->centn = o->pmap->centn + o->centn_offset;
        o->cente = o->pmap->cente + o->cente_offset;
    }
}

double* weightedMeanTSE(vector<triple<double > > data);

double* State::getEstHeadingError() { return weightedMeanTSE(headingErrors); }

double* State::getEstDistanceError() { return weightedMeanTSE(distanceErrors); }

double State::getHeading(string o1i, string o2i) { return toHeading(objects[o2i]->centn - objects[o1i]->centn, objects[o2i]->cente - objects[o1i]->cente); }

double State::getDistance(string o1i, string o2i) { return toDistance(objects[o2i]->centn - objects[o1i]->centn, objects[o2i]->cente - objects[o1i]->cente); }

double State::getN(string o1i, string o2i) { return objects[o2i]->centn - objects[o1i]->centn; }

double State::getE(string o1i, string o2i) { return objects[o2i]->cente - objects[o1i]->cente; }

void State::doCovariance(string obji, double prevn, double preve, double err) {
    
}

double* weightedMeanTSE(vector<triple<double> > data) {
    // data: x, y, err
    sort(data.begin(), data.end(), [] (triple<double> t1, triple<double> t2) { return t1.v1 < t2.v1; });
    double wsum, ssum, wx, xws, wy, yws;
    for(int i = 0; i < data.size(); i++) {
        for(int j = 0; j < data.size(); j++) {
            if (i != j) {
                double w = 1 / (data[i].v3 * data[j].v3);
                wsum += w;
                ssum += (data[j].v2 - data[i].v2) / (data[j].v1 - data[i].v1) * w;
                wx += data[j].v1 / data[j].v3;
                xws += 1 / data[j].v3;
                wy += data[i].v1 / data[i].v3;
                yws += 1 / data[i].v3;
            }
        }
    }
    double slope = ssum / wsum;
    wy /= yws;
    wx /= xws;
    double intercept = wy - (wx * slope);
    return new double [2] { intercept, slope };
}

/*
int main() {
    for (int h = 0; h <= 360; h += 10) {
        cout << toHeading(cos(h * PI / 180), sin(h * PI / 180)) << endl;
    }
    return 0;
}*/
